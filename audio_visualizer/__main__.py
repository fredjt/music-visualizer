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
import os
import subprocess
import sys

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
        "--retry", "-R", type=int, default=0, help="Number of retries on ffmpeg failure (default: 0)"
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
            "retry": args.retry,
        },
    )


if __name__ == "__main__":
    main()
