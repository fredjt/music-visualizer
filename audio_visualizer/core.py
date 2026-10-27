"""
Core functionality for audio visualizer.

Contains the main visualization logic: running ffmpeg with progress tracking,
running the visualization pipeline, listing plugins, and batch processing.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

# get_audio_duration imported lazily in run_visualizer
from audio_visualizer.logging_config import logger
from audio_visualizer.visualizers.base import VisualizerPlugin
from audio_visualizer.visualizers.registry import PluginRegistry


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
        filter_complex = plugin.build_filter(
            args.get("width", 1280),
            args.get("height", 720),
            args.get("fps", 30),
            colors=args.get("colors"),
        )

        # Build test encode command
        test_cmd = ["ffmpeg", "-y", "-i", test_wav]

        # Determine if plugin needs a background video input
        # by checking if the filter references a video stream input
        # (plugins like spectrum, bars, waveform use [1:v] for background)
        # Vectorscope and albumart don't need a background
        needs_bg = ":v]" in filter_complex or ":v," in filter_complex

        if needs_bg:
            test_cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:s={args.get('width', 1280)}x{args.get('height', 720)}:r={args.get('fps', 30)}",
                ]
            )
            test_cmd.extend(["-filter_complex", filter_complex])
            test_cmd.extend(["-map", "[out]", "-map", "0:a?"])
        else:
            test_cmd.extend(["-filter_complex", filter_complex])
            test_cmd.extend(["-map", "[viz]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        codec_settings = plugin._get_codec_settings(fmt, args, accel)
        test_cmd.extend(codec_settings)
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
                import shutil

                shutil.rmtree(tmpdir, ignore_errors=True)
                return size_mb

        import shutil

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

        try:
            for line in process.stderr:
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
                    print(f"  {line.strip()}")

                # Capture stderr lines for error reporting
                stderr_lines.append(line)

            process.wait()

        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise

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
            print("\nCancelled by user")
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
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)

    from audio_visualizer.__main__ import get_audio_duration

    duration = get_audio_duration(input_file)
    if duration:
        print(f"OK  Audio duration: {duration:.1f}s")

    # Detect hardware acceleration
    accel = detect_hwaccel(args.get("accel", "auto"))

    # Estimate output file size
    estimated_size_mb = _estimate_output_size(plugin_cls, args, duration, accel)
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

    # Build command using the plugin's method
    cmd = plugin_cls().build_command(
        {
            "input": input_file,
            "output": output_file,
            "width": args["width"],
            "height": args["height"],
            "fps": args["fps"],
            "preset": args["preset"],
            "crf": args["crf"],
            "image": args.get("image"),
            "accel": accel,
            "colors": args.get("colors"),
        }
    )

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
        fc = plugin.build_filter(
            args["width"], args["height"], args["fps"], colors=args.get("colors")
        )
        logger.debug("\nFilter complex:")
        for line in fc.split("; "):
            if line.strip():
                logger.debug(f"  {line.strip()};")
        logger.debug("")

    # Run ffmpeg with progress tracking
    retry_count = args.get("retry", 0)
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


def list_plugins(registry: PluginRegistry):
    """Display all available visualizer plugins."""
    plugins = registry.list_plugins()
    if not plugins:
        logger.info(
            "No plugins found. Run 'python3 audio_visualizer.py --install-plugin <file>' to add one."
        )
        return

    logger.info(f"\nAvailable Visualizer Plugins ({len(plugins)}):")
    logger.info("=" * 60)
    for p in plugins:
        icon = p.get("icon", "")
        name = p["name"]
        display = p["display_name"]
        desc = p["description"]
        author = f" by {p['author']}" if p.get("author") else ""
        logger.info(f"\n  {icon} {display}")
        logger.info(f"     Name: {name}{author}")
        logger.info(f"     Ver:  {p['version']}")
        logger.info(f"     Desc: {desc}")
    logger.info("")


def _process_batch(args, registry):
    """
    Process all audio files in a directory.

    Args:
        args: Parsed command-line arguments
        registry: Plugin registry instance
    """
    # Import here to avoid circular imports
    from audio_visualizer.__main__ import check_ffmpeg, run_visualizer

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

    # Supported audio extensions
    audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}

    # Find all audio files
    audio_files = []
    for file in sorted(Path(batch_dir).iterdir()):
        if file.is_file() and file.suffix.lower() in audio_extensions:
            audio_files.append(file)

    if not audio_files:
        logger.error(f"No audio files found in {batch_dir}")
        logger.error(f"  Supported formats: {', '.join(sorted(audio_extensions))}")
        sys.exit(1)

    logger.info(f"Found {len(audio_files)} audio file(s) in {batch_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("")

    # Get plugin class
    plugin_cls = registry.get(args.mode)
    if plugin_cls is None:
        available = ", ".join(registry.list_plugins())
        logger.error(f"Unknown mode '{args.mode}'")
        logger.error(f"  Available modes: {available}")
        sys.exit(1)

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

    check_ffmpeg()

    # Process each file
    success_count = 0
    fail_count = 0

    with tqdm(total=len(audio_files), desc="Batch", unit="file") as pbar:
        try:
            for i, audio_file in enumerate(audio_files, 1):
                # Show per-file status line
                logger.info(f"[{i}/{len(audio_files)}] {audio_file.name}")

                try:
                    # Set output filename in output directory
                    base_name = audio_file.stem
                    output_file = os.path.join(output_dir, f"{base_name}_visualizer.{args.format}")

                    # Check if output file exists
                    if os.path.exists(output_file) and not args.overwrite:
                        logger.info(
                            f"  SKIP: Output already exists ({os.path.basename(output_file)})"
                        )
                        logger.info("      Use --overwrite to replace")
                        fail_count += 1
                        pbar.update(1)
                        continue

                    run_visualizer(
                        plugin_cls,
                        {
                            "input": str(audio_file),
                            "output": output_file,
                            "width": width,
                            "height": height,
                            "fps": args.fps,
                            "preset": args.preset,
                            "crf": args.crf,
                            "verbose": args.verbose,
                            "image": args.image,
                            "format": args.format,
                            "accel": args.accel,
                            "colors": args.colors,
                            "retry": args.retry,
                        },
                    )
                    logger.info("  DONE ✓")
                    success_count += 1

                except Exception as e:
                    fail_count += 1
                    logger.error(f"  FAILED: {e}")
                finally:
                    pbar.update(1)

        except KeyboardInterrupt:
            logger.info("\n\nBatch processing cancelled by user")
            pbar.close()
            sys.exit(130)
        finally:
            pbar.close()

    logger.info(f"\nBatch complete: {success_count} succeeded, {fail_count} failed")
