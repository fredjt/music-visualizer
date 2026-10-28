#!/usr/bin/env python3
"""
Audio Visualizer - Plugin-based audio visualization tool.

Converts MP3/audio files into animated visualizer videos (MP4) using
a plugin architecture. Visualizers are separate plugins that can be
added, removed, or customized independently.

Usage:
    python3 audio_visualizer.py input.mp3 [options]

Examples:
    # Spectrum visualizer (default)
    python3 audio_visualizer.py song.mp3

    # Waveform visualizer
    python3 audio_visualizer.py song.mp3 --mode waveform

    # List all available plugins
    python3 audio_visualizer.py --list-plugins

    # Custom resolution and output name
    python3 audio_visualizer.py song.mp3 --resolution 1920x1080 -o output.mp4
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from audio_visualizer.config import (
    get_config_path,
    load_config,
    merge_config,
    save_config,
    validate_config,
)
from audio_visualizer.core import _process_batch, list_plugins, run_visualizer
from audio_visualizer.logging_config import DEBUG, ERROR, logger, set_level
from audio_visualizer.visualizers.registry import PluginRegistry


def check_ffmpeg():
    """Verify ffmpeg is installed and accessible."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            logger.info(f"ffmpeg found: {version_line}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    logger.error("ffmpeg is required but not found.")
    logger.error("  Install it with: apt install ffmpeg  or  brew install ffmpeg")
    sys.exit(1)


def get_audio_duration(filepath):
    """Get the duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        return float(result.stdout.strip())
    return None


def validate_plugins(registry) -> tuple[list, list]:
    """
    Validate all installed plugins.

    Args:
        registry: PluginRegistry instance with plugins loaded

    Returns:
        Tuple of (valid_plugins, invalid_plugins) where each is a list of dicts
    """
    valid = []
    invalid = []

    for name, plugin_cls in sorted(registry.get_all().items()):
        try:
            meta = plugin_cls.get_metadata()
            # Check required metadata fields
            if not meta.name:
                invalid.append(
                    {
                        "name": name,
                        "display_name": meta.display_name or "(unknown)",
                        "status": "invalid",
                        "error": "Missing plugin name in metadata",
                    }
                )
                continue

            if not meta.display_name:
                invalid.append(
                    {
                        "name": name,
                        "display_name": "(unknown)",
                        "status": "invalid",
                        "error": "Missing display_name in metadata",
                    }
                )
                continue

            if not meta.description:
                invalid.append(
                    {
                        "name": name,
                        "display_name": meta.display_name,
                        "status": "invalid",
                        "error": "Missing description in metadata",
                    }
                )
                continue

            # Test build_filter with sample parameters
            plugin = plugin_cls()
            filter_str = plugin.build_filter(1280, 720, 30, colors="blue,green,white")
            if not filter_str or not isinstance(filter_str, str):
                invalid.append(
                    {
                        "name": name,
                        "display_name": meta.display_name,
                        "status": "invalid",
                        "error": "build_filter returned empty or invalid result",
                    }
                )
                continue

            valid.append(
                {
                    "name": meta.name,
                    "display_name": meta.display_name,
                    "version": meta.version,
                    "author": meta.author or "(unknown)",
                    "description": meta.description,
                    "icon": meta.icon or "",
                    "filter_length": len(filter_str),
                }
            )

        except Exception as e:
            invalid.append(
                {
                    "name": name,
                    "display_name": "(unknown)",
                    "status": "invalid",
                    "error": str(e),
                }
            )

    return valid, invalid


def display_validation_results(valid: list, invalid: list):
    """Display validation results in a formatted table."""
    total = len(valid) + len(invalid)
    logger.info(f"\nPlugin Validation Results ({total} plugin(s))")
    logger.info("=" * 70)

    if valid:
        logger.info(f"\n  Valid Plugins ({len(valid)}):")
        logger.info("  " + "-" * 66)
        for p in valid:
            icon = p["icon"] or "  "
            logger.info(f"\n  {icon} {p['display_name']}")
            logger.info(f"     Name:       {p['name']}")
            logger.info(f"     Version:    {p['version']}")
            logger.info(f"     Author:     {p['author']}")
            logger.info(f"     Filter:     {p['filter_length']} chars")
            logger.info(f"     Description: {p['description']}")

    if invalid:
        logger.info(f"\n  Invalid Plugins ({len(invalid)}):")
        logger.info("  " + "-" * 66)
        for p in invalid:
            logger.info(f"\n  [!] {p['display_name']}")
            logger.info(f"     Name:       {p['name']}")
            logger.info(f"     Error:      {p['error']}")

    logger.info("")


def detect_hwaccel(accel_mode: str) -> str:
    """
    Detect available hardware acceleration.

    Args:
        accel_mode: User-specified acceleration mode (auto, nvenc, qsv, vaapi, disabled)

    Returns:
        Available hardware acceleration method or 'sw' for software
    """
    if accel_mode == "disabled":
        return "sw"

    try:
        result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return "sw"

        encoders = result.stdout

        if accel_mode == "auto":
            # Check in order of preference
            if "h264_nvenc" in encoders:
                return "nvenc"
            elif "h264_qsv" in encoders:
                return "qsv"
            elif "h264_vaapi" in encoders:
                return "vaapi"
            return "sw"
        elif accel_mode in ["nvenc", "qsv", "vaapi"]:
            encoder = f"h264_{accel_mode}"
            if encoder in encoders:
                return accel_mode
            logger.warning(f"{accel_mode} not available, falling back to software encoding")
            return "sw"

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return "sw"


def main():
    parser = argparse.ArgumentParser(
        description="Generate audio visualizers from MP3/audio files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Visualizer Plugins:
  spectrum   Colorful frequency spectrum (default)
  waveform   Animated waveform with gradient colors
  vectorscope Psychedelic circular visualization
  radial     Symmetrical mirrored spectrum (top/bottom reflection)
  bars       Classic horizontal bar spectrum
  showfreqs  Frequency-domain visualization with labeled bands

Plugin Management:
  --list-plugins          List all available visualizer plugins
  --install-plugin FILE   Install a plugin from a Python file

Examples:
  %(prog)s song.mp3
  %(prog)s song.mp3 --mode waveform
  %(prog)s song.mp3 --resolution 1920x1080 -o output.mp4
  %(prog)s --list-plugins
  %(prog)s ./my-album/ --batch
  %(prog)s ./my-album/ -b --mode waveform
""",
    )

    parser.add_argument("input", nargs="?", help="Input MP3 (or audio) file")
    parser.add_argument(
        "-o", "--output", default=None, help="Output file (single) or output directory (batch mode)"
    )
    parser.add_argument(
        "--mode", default="spectrum", help="Visualization mode/plugin name (default: spectrum)"
    )
    parser.add_argument(
        "--resolution", "-r", default="1280x720", help="Output resolution WxH (default: 1280x720)"
    )
    parser.add_argument("--fps", type=int, default=30, help="Frame rate (default: 30)")
    parser.add_argument(
        "--preset",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        default="medium",
        help="Encoding preset (default: medium)",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=23,
        choices=range(0, 52),
        help="Quality (18=lossless, 23=default, 28=max). Lower=better (default: 23)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed filter and command info"
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error output")
    parser.add_argument("--debug", "-d", action="store_true", help="Show debug-level output")
    parser.add_argument(
        "--list-plugins", action="store_true", help="List all available visualizer plugins"
    )
    parser.add_argument(
        "--install-plugin", metavar="FILE", help="Install a plugin from a Python file"
    )
    parser.add_argument(
        "--image", metavar="FILE", help="Image file for image visualizer plugin (album art)"
    )
    parser.add_argument(
        "--albumart-effect",
        choices=["glow", "pulse", "zoom"],
        default="glow",
        help="Album art effect: glow (default), pulse, or zoom",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="mp4",
        choices=["mp4", "mkv", "webm", "avi", "mov", "flv"],
        help="Output format (default: mp4)",
    )
    parser.add_argument(
        "--accel",
        choices=["auto", "nvenc", "qsv", "vaapi", "disabled"],
        default="auto",
        help="Hardware acceleration (default: auto)",
    )
    parser.add_argument(
        "--batch", "-b", metavar="DIRECTORY", help="Process all audio files in a directory"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing output files in batch mode"
    )
    parser.add_argument(
        "--colors",
        metavar="COLORS",
        help="Comma-separated colors for visualizer (e.g., 'blue,green,white')",
    )
    parser.add_argument(
        "--bg-color",
        metavar="COLOR",
        default=None,
        help="Background color (default: black). Accepts named colors or hex (e.g., 'navy', '#1a1a2e')",
    )
    parser.add_argument(
        "--waveform-mode",
        choices=["point", "line", "p2p", "cline", "pict"],
        default="line",
        help="Waveform display mode: line (default), point, p2p, cline, or pict (static)",
    )
    parser.add_argument(
        "--waveform-splits",
        type=int,
        default=1,
        choices=list(range(1, 9)),
        help="Number of split waveform channels (1-8, default: 1)",
    )
    parser.add_argument(
        "--waveform-frame",
        type=int,
        default=0,
        help="Samples per waveform point (0=auto)",
    )
    parser.add_argument(
        "--spectrogram-mode",
        choices=["intensity", "rain", "fire", "heat", "ice", "swirl"],
        default="intensity",
        help="Spectrogram colormapping mode (default: intensity)",
    )
    parser.add_argument(
        "--vectorscope-mode",
        choices=["frame", "line", "dot"],
        default="frame",
        help="Vectorscope draw mode: frame (filled, default), line, or dot",
    )
    parser.add_argument(
        "--vectorscope-draw",
        choices=["aaline", "line", "dot"],
        default="aaline",
        help="Vectorscope low-level draw mode: aaline (default), line, or dot",
    )
    parser.add_argument(
        "--vectorscope-color-index",
        type=int,
        default=0,
        help="Color index from palette (0=first, default: 0)",
    )
    parser.add_argument(
        "--vectorscope-scale",
        choices=["lin", "sqrt", "cbrt", "log"],
        default="cbrt",
        help="Amplitude scale mode (default: cbrt)",
    )
    parser.add_argument(
        "--vectorscope-zoom",
        type=float,
        default=1.0,
        help="Zoom factor 0.1-10 (default: 1.0)",
    )
    parser.add_argument(
        "--vectorscope-trails",
        type=int,
        default=100,
        help="Trail length 1-255 (default: 100)",
    )
    parser.add_argument(
        "--mirror-axis",
        choices=["x", "y", "xy"],
        default="y",
        help="Radial mirror axis: x (horizontal), y (vertical, default), or xy (both)",
    )
    parser.add_argument(
        "--mirror-gap",
        type=int,
        default=0,
        help="Gap in pixels between mirrored halves (default: 0)",
    )
    parser.add_argument(
        "--spectrum-mode",
        choices=[
            "channel",
            "intensity",
            "rainbow",
            "moreland",
            "nebulae",
            "fire",
            "fiery",
            "fruit",
            "cool",
            "magma",
            "green",
            "viridis",
            "plasma",
            "cividis",
            "terrain",
            "colormapping",
        ],
        default="rainbow",
        help="Spectrum color mode (default: rainbow)",
    )
    parser.add_argument(
        "--showfreqs-mode",
        choices=["line", "bar", "dot"],
        default="bar",
        help="Showfreqs display mode (default: bar)",
    )
    parser.add_argument(
        "--showfreqs-ascale",
        choices=["lin", "sqrt", "cbrt", "log"],
        default="log",
        help="Showfreqs amplitude scale (default: log)",
    )
    parser.add_argument(
        "--showfreqs-fscale",
        choices=["lin", "log", "rlog"],
        default="log",
        help="Showfreqs frequency scale (default: log)",
    )
    parser.add_argument(
        "--showfreqs-winfunc",
        choices=[
            "rect",
            "bartlett",
            "hann",
            "hamming",
            "blackman",
            "flattop",
            "bharris",
            "bnuttall",
            "bhann",
            "sine",
            "nuttall",
            "lanczos",
            "gauss",
            "tukey",
            "dolph",
            "cauchy",
            "parzen",
            "poisson",
            "bohman",
            "kaiser",
        ],
        default="hann",
        help="Showfreqs window function (default: hann)",
    )
    parser.add_argument(
        "--showfreqs-overlap",
        type=float,
        default=0.5,
        help="Showfreqs window overlap 0-1 (default: 0.5)",
    )
    parser.add_argument(
        "--showfreqs-channels",
        default="all",
        help="Showfreqs channels to draw: all, left, right, etc. (default: all)",
    )
    parser.add_argument(
        "--cqt-gamma",
        type=float,
        default=3.0,
        help="CQT sonogram gamma 1-7 (default: 3.0)",
    )
    parser.add_argument(
        "--cqt-basefreq",
        type=float,
        default=20.0,
        help="CQT base frequency Hz (default: 20.0)",
    )
    parser.add_argument(
        "--cqt-endfreq",
        type=float,
        default=20495.0,
        help="CQT end frequency Hz (default: 20495.0)",
    )
    parser.add_argument(
        "--cqt-attack",
        type=float,
        default=0.0,
        help="CQT attack time 0-1 (default: 0.0)",
    )
    parser.add_argument(
        "--cqt-timeclamp",
        type=float,
        default=0.17,
        help="CQT timeclamp 0.002-1 (default: 0.17)",
    )
    parser.add_argument(
        "--theme",
        choices=["neon", "sunset", "ocean", "forest", "dark", "light"],
        help="Predefined color theme",
    )
    parser.add_argument(
        "--config", action="store_true", help="Show current configuration file path"
    )
    parser.add_argument(
        "--save-config", action="store_true", help="Save current options to configuration file"
    )
    parser.add_argument(
        "--validate-config", action="store_true", help="Validate configuration and exit"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate all installed plugins and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without encoding"
    )
    parser.add_argument(
        "--info", metavar="FILE", help="Show detailed audio file information and exit"
    )
    parser.add_argument(
        "--retry",
        "-R",
        type=int,
        default=0,
        help="Number of retries on ffmpeg failure (default: 0)",
    )

    args = parser.parse_args()

    # Set log level based on flags
    if args.quiet:
        set_level(ERROR)
    elif args.debug:
        set_level(DEBUG)
    elif args.verbose:
        set_level(DEBUG)

    # Handle --config flag
    if args.config:
        config_path = get_config_path()
        logger.info(f"Configuration file: {config_path}")
        if os.path.exists(config_path):
            with open(config_path) as f:
                logger.info(f.read())
        else:
            logger.info("No configuration file found. Run with --save-config to create one.")
        return

    # Handle --save-config flag
    if args.save_config:
        config_path = save_config(args)
        logger.info(f"Configuration saved to: {config_path}")
        return

    # Load configuration and merge with command-line args
    config = load_config()
    args = merge_config(args, config)

    # Handle --validate-config flag
    if args.validate_config:
        issues = validate_config(config, args)
        if issues:
            logger.info("Configuration issues found:")
            for issue in issues:
                if issue.startswith("ERROR:"):
                    logger.error(issue)
                else:
                    logger.warning(issue)
            sys.exit(1)
        else:
            logger.info("Configuration is valid.")
        return

    # Handle --validate flag
    if args.validate:
        registry = PluginRegistry()
        registry.load_all()
        valid, invalid = validate_plugins(registry)
        display_validation_results(valid, invalid)
        if invalid:
            sys.exit(1)
        return

    # Handle --dry-run flag
    if args.dry_run:
        registry = PluginRegistry()
        registry.load_all()

        if args.batch:
            # Dry run for batch mode
            batch_dir = args.batch
            if not os.path.isdir(batch_dir):
                logger.error(f"Directory not found: {batch_dir}")
                sys.exit(1)

            # Determine output directory
            if args.output and os.path.isdir(args.output):
                output_dir = args.output
            elif args.output:
                output_dir = os.path.dirname(args.output) or "."
            else:
                output_dir = batch_dir

            audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
            audio_files = [
                f
                for f in sorted(Path(batch_dir).iterdir())
                if f.is_file() and f.suffix.lower() in audio_extensions
            ]

            if not audio_files:
                logger.error(f"No audio files found in {batch_dir}")
                sys.exit(1)

            logger.info(f"\nDry Run: {len(audio_files)} file(s) in {batch_dir}")
            logger.info(f"Output directory: {output_dir}")
            logger.info("")

            plugin_cls = registry.get(args.mode)
            if plugin_cls is None:
                available = ", ".join(registry.list_plugins())
                logger.error(f"Unknown mode '{args.mode}'")
                logger.error(f"  Available modes: {available}")
                sys.exit(1)

            try:
                resolution = args.resolution.split("x")
                width, height = int(resolution[0]), int(resolution[1])
            except ValueError as e:
                logger.error(f"Invalid resolution '{args.resolution}': {e}")
                sys.exit(1)

            for audio_file in audio_files:
                base_name = audio_file.stem
                output_file = os.path.join(output_dir, f"{base_name}_visualizer.{args.format}")
                logger.info(f"\n  Would encode: {audio_file.name}")
                logger.info(f"    -> {os.path.basename(output_file)}")
                plugin = plugin_cls()
                accel = detect_hwaccel(args.accel)
                cmd = plugin.build_command(
                    {
                        "input": str(audio_file),
                        "output": output_file,
                        "width": width,
                        "height": height,
                        "fps": args.fps,
                        "preset": args.preset,
                        "crf": args.crf,
                        "image": args.image,
                        "format": args.format,
                        "accel": accel,
                        "colors": args.colors,
                        "bg_color": args.bg_color,
                        "albumart_effect": getattr(args, "albumart_effect", "glow"),
                        "waveform_mode": args.waveform_mode,
                        "waveform_splits": args.waveform_splits,
                        "waveform_frame": args.waveform_frame,
                        "spectrogram_mode": getattr(args, "spectrogram_mode", "intensity"),
                        "vectorscope_mode": args.vectorscope_mode,
                        "vectorscope_color_index": getattr(args, "vectorscope_color_index", 0),
                        "vectorscope_scale": args.vectorscope_scale,
                        "vectorscope_zoom": args.vectorscope_zoom,
                        "vectorscope_trails": args.vectorscope_trails,
                        "cqt_gamma": args.cqt_gamma,
                        "cqt_basefreq": args.cqt_basefreq,
                        "cqt_endfreq": args.cqt_endfreq,
                        "cqt_attack": args.cqt_attack,
                        "cqt_timeclamp": args.cqt_timeclamp,
                    }
                )
                logger.info(f"    Command: {' '.join(cmd)}")

            logger.info("")
            logger.info(f"Dry run complete: {len(audio_files)} file(s)")
        else:
            # Dry run for single file mode
            if not args.input:
                logger.error("Input file required for dry run")
                sys.exit(1)

            plugin_cls = registry.get(args.mode)
            if plugin_cls is None:
                available = ", ".join(registry.list_plugins())
                logger.error(f"Unknown mode '{args.mode}'")
                logger.error(f"  Available modes: {available}")
                sys.exit(1)

            try:
                resolution = args.resolution.split("x")
                width, height = int(resolution[0]), int(resolution[1])
            except ValueError as e:
                logger.error(f"Invalid resolution '{args.resolution}': {e}")
                sys.exit(1)

            if args.output is None:
                base = os.path.splitext(os.path.basename(args.input))[0]
                output_file = f"{base}_visualizer.{args.format}"
            else:
                output_file = args.output

            logger.info("\nDry Run")
            logger.info(f"  Input:      {args.input}")
            logger.info(f"  Output:     {output_file}")
            logger.info(f"  Mode:       {args.mode}")
            logger.info(f"  Resolution: {width}x{height}")
            logger.info(f"  FPS:        {args.fps}")
            logger.info(f"  Preset:     {args.preset}")
            logger.info(f"  CRF:        {args.crf}")
            logger.info(f"  Format:     {args.format}")
            logger.info(f"  Acceleration: {args.accel}")

            plugin = plugin_cls()
            accel = detect_hwaccel(args.accel)
            cmd = plugin.build_command(
                {
                    "input": args.input,
                    "output": output_file,
                    "width": width,
                    "height": height,
                    "fps": args.fps,
                    "preset": args.preset,
                    "crf": args.crf,
                    "image": args.image,
                    "format": args.format,
                    "accel": accel,
                    "colors": args.colors,
                    "bg_color": args.bg_color,
                    "waveform_mode": args.waveform_mode,
                    "waveform_splits": args.waveform_splits,
                    "waveform_frame": args.waveform_frame,
                    "vectorscope_mode": args.vectorscope_mode,
                    "vectorscope_draw": args.vectorscope_draw,
                    "vectorscope_scale": args.vectorscope_scale,
                    "vectorscope_zoom": args.vectorscope_zoom,
                    "vectorscope_trails": args.vectorscope_trails,
                    "cqt_gamma": args.cqt_gamma,
                    "cqt_basefreq": args.cqt_basefreq,
                    "cqt_endfreq": args.cqt_endfreq,
                    "cqt_attack": args.cqt_attack,
                    "cqt_timeclamp": args.cqt_timeclamp,
                }
            )
            logger.info("\n  Command:")
            logger.info(f"    {' '.join(cmd)}")
            logger.info("")
            logger.info("Dry run complete (no encoding performed)")
        return

    # Handle --info flag
    if args.info:
        info_file = args.info
        if not os.path.exists(info_file):
            logger.error(f"File not found: {info_file}")
            sys.exit(1)

        # Get file size
        file_size = os.path.getsize(info_file)
        file_size_mb = file_size / (1024 * 1024)

        # Get audio info using ffprobe
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                info_file,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.error(f"ffprobe failed for {info_file}")
            logger.error(result.stderr.strip())
            sys.exit(1)

        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse ffprobe output for {info_file}")
            sys.exit(1)

        # Find audio stream
        audio_stream = None
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio_stream = stream
                break

        # Get format info
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        bitrate = int(fmt.get("bit_rate", 0))

        logger.info("\nAudio File Information")
        logger.info("=" * 50)
        logger.info(f"  File:        {os.path.basename(info_file)}")
        logger.info(f"  Path:        {os.path.abspath(info_file)}")
        logger.info(f"  Size:        {file_size_mb:.2f} MB")

        if duration > 0:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = duration % 60
            logger.info(f"  Duration:    {hours:d}:{minutes:02d}:{seconds:05.2f}")
        else:
            logger.info("  Duration:    N/A")

        if bitrate > 0:
            logger.info(f"  Bitrate:     {bitrate / 1000:.0f} kbps")
        else:
            logger.info("  Bitrate:     N/A")

        if audio_stream:
            logger.info(f"  Codec:       {audio_stream.get('codec_name', 'N/A')}")
            logger.info(f"  Sample Rate: {audio_stream.get('sample_rate', 'N/A')} Hz")
            channels = audio_stream.get("channels", 0)
            channel_layout = audio_stream.get("channel_layout", "")
            logger.info(f"  Channels:    {channels} ({channel_layout})")
            if audio_stream.get("bits_per_sample"):
                logger.info(f"  Bits/sample: {audio_stream['bits_per_sample']}")
        else:
            logger.info("  Codec:       No audio stream found")

        logger.info("")
        return

    # Initialize plugin registry
    registry = PluginRegistry()
    registry.load_all()

    if args.list_plugins:
        list_plugins(registry)
        return

    if args.install_plugin:
        if not os.path.exists(args.install_plugin):
            logger.error(f"Plugin file not found: {args.install_plugin}")
            sys.exit(1)
        registry.install_from_file(args.install_plugin)
        # Reload to pick up new plugin
        registry = PluginRegistry()
        registry.load_all()
        meta = registry.get_metadata(os.path.splitext(os.path.basename(args.install_plugin))[0])
        if meta:
            logger.info(f"Plugin installed: {meta.display_name}")
            logger.info(f"     Name: {meta.name}")
            logger.info(f"     Run with: --mode {meta.name}")
        else:
            # Try to find by scanning
            for name, cls in registry.get_all().items():
                m = cls.get_metadata()
                if os.path.basename(args.install_plugin).replace(".py", "") in name:
                    logger.info(f"Plugin installed: {m.display_name}")
                    logger.info(f"     Name: {m.name}")
                    logger.info(f"     Run with: --mode {m.name}")
                    break
        return

    # Handle batch processing
    if args.batch:
        _process_batch(args, registry)
        return

    # Validate input
    if not args.input:
        parser.print_help()
        sys.exit(1)

    # Get plugin class
    plugin_cls = registry.get(args.mode)
    if plugin_cls is None:
        available = ", ".join(p["name"] for p in registry.list_plugins())
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

    # Set default output name
    if args.output is None:
        base = os.path.splitext(os.path.basename(args.input))[0]
        args.output = f"{base}_visualizer.{args.format}"

    check_ffmpeg()

    run_visualizer(
        plugin_cls,
        {
            "input": args.input,
            "output": args.output,
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
            "bg_color": args.bg_color,
            "albumart_effect": args.albumart_effect,
            "waveform_mode": args.waveform_mode,
            "waveform_splits": args.waveform_splits,
            "waveform_frame": args.waveform_frame,
            "vectorscope_mode": args.vectorscope_mode,
            "vectorscope_draw": args.vectorscope_draw,
            "vectorscope_scale": args.vectorscope_scale,
            "vectorscope_zoom": args.vectorscope_zoom,
            "vectorscope_trails": args.vectorscope_trails,
            "spectrogram_mode": args.spectrogram_mode,
            "cqt_gamma": args.cqt_gamma,
            "cqt_basefreq": args.cqt_basefreq,
            "cqt_endfreq": args.cqt_endfreq,
            "cqt_attack": args.cqt_attack,
            "cqt_timeclamp": args.cqt_timeclamp,
            "mirror_axis": args.mirror_axis,
            "mirror_gap": args.mirror_gap,
            "spectrum_mode": args.spectrum_mode,
            "showfreqs_mode": args.showfreqs_mode,
            "showfreqs_ascale": args.showfreqs_ascale,
            "showfreqs_fscale": args.showfreqs_fscale,
            "showfreqs_winfunc": args.showfreqs_winfunc,
            "showfreqs_overlap": args.showfreqs_overlap,
            "showfreqs_channels": args.showfreqs_channels,
            "retry": args.retry,
        },
    )


if __name__ == "__main__":
    main()
