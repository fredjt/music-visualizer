"""
Core functionality for audio visualizer.

Contains the main visualization logic: running ffmpeg with progress tracking,
running the visualization pipeline, listing plugins, and batch processing.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

# get_audio_duration imported lazily in run_visualizer
from audio_visualizer.logging_config import logger
from audio_visualizer.visualizers._composite import CompositeVisualizer
from audio_visualizer.visualizers.base import VisualizerPlugin
from audio_visualizer.visualizers.registry import PluginRegistry


def resolve_mode_classes(args, registry) -> list[type[VisualizerPlugin]]:
    """Normalize ``args.mode`` to a list and resolve each name to a plugin class.

    Accepts either a single string (config/env origins) or a list (the
    CLI's ``nargs="+"``). Tokens may use the ``a+b`` combo sugar
    (``--mode spectrum+waveform``). Unknown, duplicated, or malformed
    modes exit with an error.
    """
    if isinstance(args.mode, str):
        args.mode = [args.mode]
    expanded: list[str] = []
    for token in args.mode:
        for part in token.split("+"):
            if not part:
                logger.error(f"Invalid mode '{token}' (empty combo element — check the '+')")
                sys.exit(1)
            expanded.append(part)
    args.mode = expanded
    classes: list[type[VisualizerPlugin]] = []
    for name in expanded:
        cls = registry.get(name)
        if cls is None:
            available = ", ".join(p["name"] for p in registry.list_plugins())
            logger.error(f"Unknown mode '{name}'")
            logger.error(f"  Available modes: {available}")
            sys.exit(1)
        if any(cls is c for c in classes):
            logger.error(f"Duplicate mode '{name}' — each mode may appear once")
            sys.exit(1)
        classes.append(cls)
    return classes


def mode_label(args) -> str:
    """Human-facing label for the selected mode(s).

    Used in output templates, dry-run/JSON payloads, and batch reports:
    ``spectrum`` stays ``spectrum``; ``spectrum waveform`` becomes
    ``spectrum+waveform``.
    """
    if isinstance(args.mode, str):
        return args.mode
    return "+".join(args.mode)


# Named multi-mode combos offered in --list-plugins. The '+' sugar
# (resolve_mode_classes) accepts any combination of loaded modes; these
# are the standard built-in combinations.
COMBO_PRESETS: tuple[tuple[str, str], ...] = (
    ("spectrum+waveform", "Frequency bars beside the waveform"),
    ("spectrum+vectorscope", "Spectrum beside the L/R vectorscope"),
)


def _estimate_output_size(plugin_cls, args: dict, duration: float, accel: str) -> float:
    """
    Estimate the output file size in MB.

    For CRF/CQ encoded videos, the bitrate is content-dependent and cannot
    be predicted by a static formula. Instead, we do a short test encode
    to measure the actual bitrate, then extrapolate.

    Falls back to a formula-based estimate for very short audio or if
    the test encode fails.

    Args:
        plugin_cls: The visualizer plugin class
        args: Arguments dict with width, height, fps, preset, crf, format, input, accel
        duration: Audio duration in seconds
        accel: Hardware acceleration method

    Returns:
        Estimated size in MB, or 0 if estimation not possible
    """
    if duration <= 0:
        return 0

    # For very short audio (< 3s), just use formula
    if duration < 3:
        return _estimate_output_size_formula(args, duration, accel)

    # Do a short test encode to measure actual bitrate
    import tempfile

    try:
        tmpdir = tempfile.mkdtemp()
        test_duration = min(3.0, duration)  # Encode 3 seconds or full duration if shorter
        test_wav = os.path.join(tmpdir, "_test.wav")
        test_mp4 = os.path.join(tmpdir, "_test.mp4")

        # Extract test segment from input audio
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                args["input"],
                "-t",
                str(test_duration),
                "-ar",
                "44100",
                "-ac",
                "2",
                test_wav,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to extract test segment")

        # Build the same filter that will be used for the full encode
        plugin = plugin_cls()

        # Albumart plugin needs special handling - it uses an image input,
        # not a black background. Skip test-encode for albumart.
        if plugin_cls.__name__ == "AlbumArtPlugin":
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError("Albumart plugin skipped for test-encode")

        filter_complex = plugin.build_filter_complex(args)

        # Build test encode command: same inputs as the full encode (from
        # the plugin's get_inputs hook), except the audio input is
        # replaced with the short test segment.
        test_cmd = ["ffmpeg", "-y", "-i", test_wav]
        for input_args in plugin.get_inputs(args)[1:]:
            test_cmd.extend(input_args)
        test_cmd.extend(["-filter_complex", filter_complex])
        test_cmd.extend(["-map", "[out]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        test_cmd.extend(plugin.get_codec_settings(fmt, args, accel))
        test_cmd.extend(["-shortest", test_mp4])

        # Run test encode
        result = subprocess.run(
            test_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if not os.path.exists(test_mp4) or os.path.getsize(test_mp4) < 100:
            raise RuntimeError("Test encode produced no output")

        # Measure actual bitrate from test encode
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration,bit_rate",
                "-of",
                "csv=p=0",
                test_mp4,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            parts = probe.stdout.strip().split(",")
            actual_duration = float(parts[0]) if parts[0] else test_duration
            actual_bitrate = int(parts[1]) if len(parts) > 1 and parts[1] else 0

            if actual_duration > 0 and actual_bitrate > 0:
                # Extrapolate to full duration
                # Add a small buffer for GOP overhead (~2%)
                size_mb = (actual_bitrate * duration * 1.02) / (8 * 1024 * 1024)
                shutil.rmtree(tmpdir, ignore_errors=True)
                return size_mb

        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError("Could not measure bitrate from test encode")

    except Exception:
        # Fall back to formula-based estimate
        return _estimate_output_size_formula(args, duration, accel)


def _estimate_output_size_formula(args: dict, duration: float, accel: str) -> float:
    """
    Formula-based bitrate estimation for CRF mode.

    This is a rough estimate only. Actual bitrate for CRF mode depends
    on content complexity and can vary significantly.

    Args:
        args: Arguments dict with width, height, fps, preset, crf, format
        duration: Audio duration in seconds
        accel: Hardware acceleration method

    Returns:
        Estimated size in MB
    """
    if duration <= 0:
        return 0

    # Estimate video bitrate based on preset, CRF, resolution, and fps
    width = args.get("width", 1280)
    height = args.get("height", 720)
    fps = args.get("fps", 30)
    preset = args.get("preset", "medium")
    crf = args.get("crf", 23)

    # FPS scaling factor (30fps = baseline, higher fps = more data)
    fps_factor = fps / 30.0

    # Base bitrate factors from preset (higher preset = lower quality = lower bitrate)
    preset_factors = {
        "ultrafast": 0.5,
        "superfast": 0.6,
        "veryfast": 0.7,
        "faster": 0.8,
        "fast": 0.9,
        "medium": 1.0,
        "slow": 1.1,
        "slower": 1.2,
        "veryslow": 1.3,
    }
    base_factor = preset_factors.get(preset, 1.0)

    # CRF adjustment (lower CRF = higher quality = higher bitrate)
    crf_factor = (51 - crf) / 28.0

    # Resolution factor (720p = 1.0, 1080p = ~1.8, 4K = ~7.1)
    res_factor = (width * height) / (1280 * 720)

    # Hardware encoding produces larger files than software
    hw_factor = 1.5 if accel in ("nvenc", "qsv", "vaapi") else 1.0

    # Base bitrate for 720p 30fps medium CRF23 with simple content
    # This is a rough baseline; actual CRF bitrate varies by content
    base_bitrate = 2000  # kbps
    video_bitrate_kbps = (
        base_bitrate * base_factor * crf_factor * res_factor * fps_factor * hw_factor
    )
    video_bitrate_kbps = max(500, min(video_bitrate_kbps, 80000))  # Clamp 500-80000 kbps

    # Audio bitrate (estimate based on input file)
    audio_bitrate_kbps = 128  # Default MP3 bitrate
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=bit_rate",
                "-of",
                "csv=p=0",
                args["input"],
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            audio_bitrate_kbps = int(result.stdout.strip()) // 1000
    except Exception:
        pass

    # Total bitrate in kbps
    total_bitrate_kbps = video_bitrate_kbps + audio_bitrate_kbps

    # Size in MB
    size_mb = (total_bitrate_kbps * duration) / (8 * 1024)
    return size_mb


def build_args_dict(args, **overrides) -> dict:
    """
    Build the full args dict passed to a plugin's build_command()/run_visualizer().

    Starts from the entire parsed CLI namespace so every option — including
    the per-plugin schema options auto-generated by build_plugin_args() —
    reaches the plugin, then applies any keyword overrides (input, output,
    width, height, fps, ...).

    Args:
        args: Parsed argparse namespace.
        **overrides: Values that override the corresponding CLI attributes.

    Returns:
        Dictionary with all CLI options plus the overrides.
    """
    d = {k: v for k, v in vars(args).items() if not k.startswith("_")}
    for key, value in overrides.items():
        if value is not None:
            d[key] = value
    return d


def _run_with_progress(cmd: list, duration: float, verbose: bool = False, retry_count: int = 0):
    """
    Run ffmpeg with a progress bar and ETA, with optional retry on failure.

    Args:
        cmd: ffmpeg command list
        duration: Expected duration in seconds
        verbose: Whether to show verbose output
        retry_count: Number of retries on failure (0 = no retries)
    """
    # Create progress bar
    pbar = tqdm(
        total=int(duration),
        desc="Encoding",
        unit="s",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        initial=0,
    )

    def _execute():
        """Execute ffmpeg and return (process, stderr_lines)."""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Support multiple time formats from different ffmpeg versions
        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)|time=(\d+):(\d+):(\d+)")
        last_time = 0
        stderr_lines = []
        stderr_file = process.stderr
        stdout_file = process.stdout
        if stderr_file is None:
            # Popen was called with stderr=PIPE; this can't happen in
            # practice and keeps the loop type-safe.
            raise RuntimeError("ffmpeg process stderr is unavailable")

        try:
            for line in stderr_file:
                # Check for time information
                time_match = time_pattern.search(line)
                if time_match:
                    # Handle both float and integer seconds
                    if time_match.group(3) is not None:
                        # Format: HH:MM:SS.ss
                        hours, minutes, seconds = (
                            time_match.group(1),
                            time_match.group(2),
                            time_match.group(3),
                        )
                        current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    else:
                        # Format: HH:MM:SS
                        hours, minutes, seconds = (
                            time_match.group(4),
                            time_match.group(5),
                            time_match.group(6),
                        )
                        current_time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)

                    # Update progress bar
                    if current_time > last_time:
                        pbar.n = min(int(current_time), int(duration))
                        pbar.refresh()
                        last_time = current_time

                # Show verbose output if enabled
                if verbose and not time_match:
                    logger.debug(f"  {line.strip()}")

                # Capture stderr lines for error reporting
                stderr_lines.append(line)

            process.wait()

        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise
        finally:
            if stderr_file is not None and hasattr(stderr_file, "close"):
                stderr_file.close()
            if stdout_file is not None and hasattr(stdout_file, "close"):
                stdout_file.close()

        return process, stderr_lines

    last_error_lines = []
    attempt = 0
    max_attempts = retry_count + 1

    while attempt < max_attempts:
        attempt += 1
        try:
            pbar.reset(int(duration))
            pbar.n = 0
            pbar.refresh()

            process, stderr_lines = _execute()

            if process.returncode != 0:
                # ffmpeg failed
                last_error_lines = stderr_lines
                if attempt < max_attempts:
                    backoff = min(2 ** (attempt - 1), 10)  # Cap at 10 seconds
                    logger.warning(
                        f"ffmpeg failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {backoff}s..."
                    )
                    pbar.close()
                    time.sleep(backoff)
                    continue
                else:
                    logger.error("ffmpeg failed:")
                    for line in last_error_lines[-20:]:
                        logger.error(f"  {line.strip()}")
                    pbar.close()
                    sys.exit(1)

            break  # Success

        except KeyboardInterrupt:
            pbar.close()
            logger.info("\nCancelled by user")
            sys.exit(130)
        except Exception as e:
            logger.error(f"Unexpected error (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                backoff = min(2 ** (attempt - 1), 10)
                logger.warning(f"Retrying in {backoff}s...")
                pbar.close()
                time.sleep(backoff)
                continue
            pbar.close()
            sys.exit(1)
        finally:
            # Ensure progress bar is closed and completed
            if pbar.n < pbar.total:
                pbar.n = pbar.total
                pbar.refresh()
            pbar.close()

    logger.info(f"Completed in {attempt} attempt(s)")


def run_visualizer(plugin_cls: type[VisualizerPlugin], args: dict):
    """
    Run the visualization pipeline using a plugin.

    Args:
        plugin_cls: The visualizer plugin class to use
        args: Dictionary with keys: input, output, width, height, fps,
              preset, crf, verbose, accel
    """
    # Import here to avoid circular imports
    from audio_visualizer.__main__ import detect_hwaccel

    input_file = args["input"]
    output_file = args["output"]

    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)

    from audio_visualizer.__main__ import get_audio_duration

    duration = get_audio_duration(input_file)
    if duration:
        logger.info(f"Audio duration: {duration:.1f}s")

    # Detect hardware acceleration
    accel = detect_hwaccel(args.get("accel", "auto"))

    # Estimate output file size (duration may be None if ffprobe failed)
    estimated_size_mb = _estimate_output_size(plugin_cls, args, duration or 0, accel)
    if estimated_size_mb > 0:
        logger.info(f"   Estimated size: {estimated_size_mb:.2f} MB")
        # Check available disk space
        try:
            stat = os.statvfs(os.path.dirname(os.path.abspath(output_file)) or ".")
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb < estimated_size_mb * 1.5:  # 50% margin
                logger.warning(
                    f"   Warning: Only {free_mb:.1f} MB free, ~{estimated_size_mb:.1f} MB needed"
                )
        except OSError:
            pass

    # Get plugin metadata
    meta = plugin_cls.get_metadata()

    # Build command using the plugin's method. Pass the full args dict so
    # every user option (plugin options, bg_color, border, format) reaches
    # the encode; the detected accel overrides the raw "auto" choice.
    cmd_args = dict(args)
    cmd_args["accel"] = accel
    try:
        cmd = plugin_cls().build_command(cmd_args)
    except FileNotFoundError as e:
        # e.g., albumart --image points to a missing file
        logger.error(str(e))
        sys.exit(1)

    # Print info
    logger.info("Generating visualizer...")
    logger.info(f"   Plugin:       {meta.icon or ''} {meta.display_name}")
    logger.info(f"   Description:  {meta.description}")
    logger.info(f"   Resolution:   {args['width']}x{args['height']}")
    logger.info(f"   FPS:          {args['fps']}")
    logger.info(f"   Preset:       {args['preset']}")
    logger.info(f"   CRF:          {args['crf']}")
    logger.info(f"   Acceleration: {accel}")

    if args["verbose"]:
        # Rebuild filter to show it
        plugin = plugin_cls()
        logger.debug(f"   Command: {' '.join(cmd)}")
        fc = plugin.build_filter_complex(args)
        logger.debug("\nFilter complex:")
        for line in fc.split("; "):
            if line.strip():
                logger.debug(f"  {line.strip()};")
        logger.debug("")

    # Run ffmpeg with progress tracking (clamp negative/invalid retry counts)
    retry_count = max(0, int(args.get("retry", 0) or 0))
    if duration and duration > 0:
        _run_with_progress(cmd, duration, args.get("verbose", False), retry_count)
    else:
        # No duration info — run without progress bar, with optional retry
        max_attempts = retry_count + 1
        for attempt in range(1, max_attempts + 1):
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode == 0:
                break
            if attempt < max_attempts:
                backoff = min(2 ** (attempt - 1), 10)
                logger.warning(
                    f"ffmpeg failed (attempt {attempt}/{max_attempts}), retrying in {backoff}s..."
                )
                time.sleep(backoff)
            else:
                logger.error("ffmpeg failed:")
                stderr = process.stderr.strip()
                lines = stderr.split("\n")
                for line in lines[-20:]:
                    logger.error(f"  {line}")
                sys.exit(1)

    # Check output file
    if os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"\nVisualizer saved to: {output_file}")
        logger.info(f"     Size: {size_mb:.2f} MB")
    else:
        logger.error(f"Output file not created: {output_file}")
        sys.exit(1)


def list_plugins(registry: PluginRegistry, category: str | None = None, verbose: bool = False):
    """Display available visualizer plugins.

    Args:
        registry: Plugin registry instance.
        category: If provided, only show plugins in this category.
        verbose: If True, show each plugin's options, ffmpeg requirements,
                 and input types.
    """
    plugins = registry.list_plugins(category=category)
    if not plugins:
        if category:
            logger.info(f"No plugins found in category '{category}'.")
        else:
            logger.info(
                "No plugins found. Run 'python3 audio_visualizer.py --install-plugin <file>' to add one."
            )
        return

    title = f"Available Visualizer Plugins ({len(plugins)})"
    if category:
        title += f" in category '{category}'"
    logger.info(f"\n{title}:")
    logger.info("=" * 60)

    # Group by category for display
    by_category: dict[str, list[dict]] = {}
    for p in plugins:
        by_category.setdefault(p["category"], []).append(p)

    for cat in sorted(by_category):
        logger.info(f"\n  [{cat}]")
        for p in by_category[cat]:
            icon = p.get("icon", "")
            name = p["name"]
            display = p["display_name"]
            desc = p["description"]
            author = f" by {p['author']}" if p.get("author") else ""
            origin = p.get("origin", "builtin")
            source = f"  [{origin}]" if origin != "builtin" else ""
            logger.info(f"    {icon} {display}")
            logger.info(f"       Name: {name}{source}{author}")
            logger.info(f"       Ver:  {p['version']}")
            logger.info(f"       Desc: {desc}")
            if verbose:
                logger.info(f"       Source: {origin}")
                plugin_cls = registry.get(name)
                if plugin_cls is not None:
                    opts = plugin_cls.get_options()
                    if opts:
                        logger.info("       Options:")
                        for opt_name, opt in opts.items():
                            choices = (
                                f"  choices: {', '.join(str(c) for c in opt.choices)}"
                                if opt.choices
                                else ""
                            )
                            logger.info(
                                f"         --{opt_name.replace('_', '-')}"
                                f"  [{opt.type.__name__}]  default={opt.default!r}{choices}"
                            )
                            if opt.help:
                                logger.info(f"           {opt.help}")
                if p.get("requires_ffmpeg_version"):
                    logger.info(f"       Requires ffmpeg >= {p['requires_ffmpeg_version']}")
                if p.get("input_types"):
                    logger.info(f"       Inputs: {', '.join(p['input_types'])}")

    # Named multi-mode combos (only when all members are loadable)
    if not category:
        combos = [
            (name, desc)
            for name, desc in COMBO_PRESETS
            if all(registry.get(part) for part in name.split("+"))
        ]
        if combos:
            logger.info("\n  [combos]  multi-mode presets — use as one --mode value")
            for name, desc in combos:
                logger.info(f"    {name}")
                logger.info(f"       {desc}")
    logger.info("")


# Audio extensions accepted by batch discovery (default include)
BATCH_AUDIO_EXTENSIONS = ".mp3 .wav .flac .ogg .m4a .aac .wma".split()

# Default batch output filename (matches the pre-template behavior)
OUTPUT_TEMPLATE_DEFAULT = "{name}_visualizer.{ext}"

# Placeholders accepted by --output-template
OUTPUT_TEMPLATE_PLACEHOLDERS = ("name", "ext", "mode", "width")


def render_output_template(template: str, name: str, ext: str, mode: str, width: int) -> str:
    """
    Render a batch output filename from the naming template.

    Placeholders:
        {name}  — audio file name without extension
        {ext}   — output format (e.g. 'mp4')
        {mode}  — plugin name (e.g. 'spectrum')
        {width} — output width in pixels
    """
    return template.format(name=name, ext=ext, mode=mode, width=width)


def discover_batch_files(
    batch_dir: str,
    recursive: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[Path]:
    """
    Discover audio files in a batch directory.

    Args:
        batch_dir: Directory to scan.
        recursive: Also scan subdirectories.
        include: Glob patterns (fnmatch) a file's path relative to
            batch_dir must match; default (empty) is the built-in audio
            extension list.
        exclude: Glob patterns; matching files are dropped (applied after
            include).

    Returns:
        Sorted list of matching file paths.
    """
    import fnmatch

    include = include or []
    exclude = exclude or []
    root = Path(batch_dir)
    candidates = root.rglob("*") if recursive else root.iterdir()

    files = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if include:
            if not any(fnmatch.fnmatch(rel, pattern) for pattern in include):
                continue
        elif path.suffix.lower() not in BATCH_AUDIO_EXTENSIONS:
            continue
        if any(fnmatch.fnmatch(rel, pattern) for pattern in exclude):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def check_output_template(template: str, ext: str, mode: str, width: int) -> str:
    """
    Render the template with probe values and validate it.

    Raises ValueError for unrenderable templates (unknown or malformed
    placeholders, directory separators, empty result) so callers can
    fail fast before processing any file.
    """
    if "/" in template or os.sep in template:
        raise ValueError("must not contain directory separators")
    try:
        rendered = render_output_template(template, "probe", ext, mode, width)
    except (KeyError, ValueError, IndexError) as e:
        raise ValueError(f"unrenderable template: {e}") from e
    if not rendered:
        raise ValueError("resolves to an empty filename")
    return rendered


def resolve_parallel_count(spec: str) -> int:
    """
    Parse a --parallel value: a positive integer, or 'auto' for a
    CPU-aware default. Raises ValueError for anything else.
    """
    text = str(spec).strip().lower()
    if text == "auto":
        return max(1, os.cpu_count() or 1)
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"'{spec}' is not a positive integer or 'auto'") from None
    if value < 1:
        raise ValueError("parallel count must be >= 1")
    return value


def _batch_timestamp() -> str:
    """ISO-8601 local timestamp for batch report entries."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_batch_report(output_dir: str, report: dict) -> None:
    """Write <output_dir>/batch_report.json (never raises)."""
    report_path = os.path.join(output_dir, "batch_report.json")
    try:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Batch report: {report_path}")
    except OSError as e:
        logger.warning(f"Could not write batch report: {e}")


def _process_batch(args, registry):
    """
    Process all audio files in a directory.

    Args:
        args: Parsed command-line arguments
        registry: Plugin registry instance
    """
    # Import here to avoid circular imports
    from audio_visualizer.__main__ import check_ffmpeg, get_audio_duration, run_visualizer

    batch_dir = args.batch

    if not os.path.isdir(batch_dir):
        logger.error(f"Directory not found: {batch_dir}")
        sys.exit(1)

    # Determine output directory
    if args.output and os.path.isdir(args.output):
        output_dir = args.output
    elif args.output:
        # If output is a file path, use its directory
        output_dir = os.path.dirname(args.output) or "."
    else:
        output_dir = batch_dir

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Find audio files (extension filter by default; --recursive/--include/
    # --exclude discovery options) — see discover_batch_files()
    audio_files = discover_batch_files(
        batch_dir,
        recursive=args.recursive,
        include=args.include,
        exclude=args.exclude,
    )

    if not audio_files:
        logger.error(f"No audio files found in {batch_dir}")
        logger.error(f"  Supported formats: {', '.join(sorted(BATCH_AUDIO_EXTENSIONS))}")
        logger.error("  Use --recursive, --include, and --exclude to adjust discovery")
        sys.exit(1)

    logger.info(f"Found {len(audio_files)} audio file(s) in {batch_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("")

    # Resolve the selected mode(s); two or more become a composite
    mode_classes = resolve_mode_classes(args, registry)
    if len(mode_classes) > 1:
        plugin_cls = CompositeVisualizer
    else:
        plugin_cls = mode_classes[0]

    # Parse resolution
    try:
        resolution = args.resolution.split("x")
        if len(resolution) != 2:
            raise ValueError("Resolution must be in WxH format")
        width, height = int(resolution[0]), int(resolution[1])
        if width <= 0 or height <= 0:
            raise ValueError("Resolution dimensions must be positive")
    except ValueError as e:
        logger.error(f"Invalid resolution '{args.resolution}': {e}")
        logger.error("  Use format: WxH (e.g., 1920x1080)")
        sys.exit(1)

    # Validate the output template up front so a typo fails before any
    # file is processed
    try:
        check_output_template(args.output_template, args.format, mode_label(args), width)
    except ValueError as e:
        logger.error(f"Invalid --output-template '{args.output_template}': {e}")
        logger.error(
            f"  Valid placeholders: {', '.join('{' + p + '}' for p in OUTPUT_TEMPLATE_PLACEHOLDERS)}"
        )
        sys.exit(1)

    check_ffmpeg()

    # Resolve --parallel (default 1 = today's sequential behavior)
    parallel_spec = getattr(args, "parallel", "1")
    try:
        parallel = resolve_parallel_count(parallel_spec)
    except ValueError as e:
        logger.error(f"Invalid --parallel '{parallel_spec}': {e}")
        logger.error("  Use a positive integer or 'auto'")
        sys.exit(1)

    # Process each file
    report_files: list[dict] = []

    def _safe_size(file_path: str):
        try:
            return os.path.getsize(file_path)
        except OSError:
            return None

    def _entry(
        status: str, input_file: Path, output_path: str | None, size, duration, error
    ) -> dict:
        return {
            "input": str(input_file),
            "output": output_path,
            "status": status,
            "size": size,
            "duration": duration,
            "error": error,
            "timestamp": _batch_timestamp(),
        }

    def _log_batch_entry(entry: dict, name: str | None = None) -> None:
        label = f" {name}" if name else ""
        if entry["status"] == "success":
            logger.info(f"  DONE \u2713{label}")
        elif entry["status"] == "skipped":
            logger.info(
                f"  SKIP: Output already exists ({os.path.basename(entry['output'])}){label}"
            )
            logger.info("      Use --overwrite to replace")
        else:
            logger.error(f"  FAILED{label}: {entry['error']}")

    def _process_one(audio_file: Path) -> dict:
        """
        Handle one file (skip check + encode) and return its report entry.

        Per-file failures are captured as a 'failed' entry; a SystemExit
        other than 1 (e.g. 130 from Ctrl+C) aborts the whole batch.
        """
        output_file = None
        try:
            # Set output filename in output directory (template-driven)
            base_name = audio_file.stem
            output_name = render_output_template(
                args.output_template, base_name, args.format, mode_label(args), width
            )
            output_file = os.path.join(output_dir, output_name)

            # Check if output file exists
            if os.path.exists(output_file) and not args.overwrite:
                return _entry(
                    "skipped",
                    audio_file,
                    output_file,
                    _safe_size(output_file),
                    None,
                    None,
                )

            run_visualizer(
                plugin_cls,
                build_args_dict(
                    args,
                    input=str(audio_file),
                    output=output_file,
                    width=width,
                    height=height,
                    mode_classes=mode_classes,
                ),
            )
            try:
                entry_duration = get_audio_duration(str(audio_file))
            except (Exception, SystemExit):
                entry_duration = None
            return _entry(
                "success",
                audio_file,
                output_file,
                _safe_size(output_file),
                entry_duration,
                None,
            )
        except (Exception, SystemExit) as e:
            # A SystemExit(1) from an ffmpeg failure inside run_visualizer
            # should fail this file and continue with the next one; a
            # SystemExit(130) from Ctrl+C must abort.
            if isinstance(e, SystemExit) and e.code not in (None, 0, 1):
                raise
            error = f"process exited with code {e.code}" if isinstance(e, SystemExit) else str(e)
            return _entry("failed", audio_file, output_file, None, None, error)

    cancelled = False
    with tqdm(total=len(audio_files), desc="Batch", unit="file") as pbar:
        if parallel <= 1:
            # Sequential (default): today's behavior
            for i, audio_file in enumerate(audio_files, 1):
                logger.info(f"[{i}/{len(audio_files)}] {audio_file.name}")
                entry = _process_one(audio_file)
                _log_batch_entry(entry)
                report_files.append(entry)
                pbar.update(1)
        else:
            # N concurrent ffmpeg jobs; the progress bar tracks completed
            # files, so it stays accurate regardless of finish order.
            # (On Ctrl+C, pending jobs are cancelled and in-flight encodes
            # are allowed to finish before the report is written.)
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                futures = {}
                for i, audio_file in enumerate(audio_files, 1):
                    logger.info(f"[{i}/{len(audio_files)}] {audio_file.name}")
                    futures[executor.submit(_process_one, audio_file)] = audio_file
                try:
                    for future in as_completed(futures):
                        entry = future.result()
                        _log_batch_entry(entry, futures[future].name)
                        report_files.append(entry)
                        pbar.update(1)
                except KeyboardInterrupt:
                    logger.info("\n\nBatch processing cancelled by user")
                    cancelled = True
                    for f in futures:
                        f.cancel()
            # Restore input order for a stable report
            order = {str(af): k for k, af in enumerate(audio_files)}
            report_files.sort(key=lambda e: order[e["input"]])

    success_count = sum(1 for e in report_files if e["status"] == "success")
    fail_count = sum(1 for e in report_files if e["status"] == "failed")
    skip_count = sum(1 for e in report_files if e["status"] == "skipped")

    logger.info(
        f"\nBatch complete: {success_count} succeeded, {fail_count} failed, {skip_count} skipped"
    )

    # Always write the report (even on failures or cancellation)
    report = {
        "batch_dir": batch_dir,
        "output_dir": output_dir,
        "mode": mode_label(args),
        "format": args.format,
        "counts": {
            "total": len(audio_files),
            "success": success_count,
            "failed": fail_count,
            "skipped": skip_count,
        },
        "files": report_files,
        "timestamp": _batch_timestamp(),
    }
    _write_batch_report(output_dir, report)

    if cancelled:
        sys.exit(130)
    if fail_count > 0:
        # Non-zero exit only when at least one file failed; the report is
        # written either way (see batch_report.json)
        sys.exit(1)
