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


def build_plugin_args(parser: argparse.ArgumentParser, registry: PluginRegistry) -> None:
    """
    Auto-generate CLI arguments from plugin option schemas.

    Iterates over all loaded plugins and adds an argument for each
    PluginOption in the plugin's options list. Arguments are grouped
    by plugin for cleaner --help output.
    """
    for name, plugin_cls in sorted(registry.get_all().items()):
        meta = plugin_cls.get_metadata()
        options = plugin_cls.get_options()

        if not options:
            continue

        group = parser.add_argument_group(f"{meta.display_name} options")

        for opt_name, opt in options.items():
            arg_name = f"--{opt_name.replace('_', '-')}"

            kwargs: dict = {
                "default": opt.default,
                "help": opt.help or f"Default: {opt.default}",
            }

            if opt.type is bool:
                kwargs["action"] = "store_true"
            else:
                kwargs["type"] = opt.type

            if opt.choices is not None:
                kwargs["choices"] = opt.choices

            group.add_argument(arg_name, **kwargs)


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

    # Get all loaded plugins and any that failed validation
    all_plugins = registry.get_all()
    load_errors = []
    if hasattr(registry, "get_all_with_errors"):
        all_plugins, load_errors = registry.get_all_with_errors()

    # Add plugins that failed during load
    for error_info in load_errors:
        invalid.append(
            {
                "name": error_info["name"],
                "display_name": "(unknown)",
                "status": "invalid",
                "error": error_info["error"],
            }
        )

    for name, plugin_cls in sorted(all_plugins.items()):
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
            filter_str = plugin.build_filter(1280, 720, 30, options={"colors": "blue,green,white"})
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
    # Load plugin registry early so we can auto-generate CLI flags from schemas
    registry = PluginRegistry()
    registry.load_all()

    parser = argparse.ArgumentParser(
        description="Generate audio visualizers from MP3/audio files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Visualizer Plugins:
  spectrum          Colorful frequency spectrum (default)
  waveform          Animated waveform with gradient colors
  vectorscope       Psychedelic circular visualization
  radial            Symmetrical mirrored spectrum (top/bottom reflection)
  bars              Classic horizontal bar spectrum
  showfreqs         Frequency-domain visualization with labeled bands
  showvolume        Reactive volume meter (peak or RMS)
  cqt               Constant Q Transform (music-theory-friendly)
  spectrogram       Scrolling waterfall spectrogram
  albumart          Album art with audio-reactive effects
  circular-spectrum True radial/circular spectrum

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
    # Auto-generate plugin-specific flags from plugin option schemas
    build_plugin_args(parser, registry)
    # Shared visualizer options
    parser.add_argument(
        "--border",
        action="store_true",
        help="Add a colored border around the visualization",
    )
    parser.add_argument(
        "--border-color",
        default="ffffff",
        help="Border color hex (default: ffffff)",
    )
    parser.add_argument(
        "--border-width",
        type=int,
        default=2,
        help="Border width in pixels (default: 2)",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=["16:9", "4:3", "1:1", "21:9"],
        default=None,
        help="Aspect ratio (auto-calculates resolution). Overrides --resolution",
    )
    parser.add_argument(
        "--visualizer-config",
        metavar="FILE",
        help="Save/load per-visualizer preset configuration file",
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
                        "mirror_axis": args.mirror_axis,
                        "mirror_gap": args.mirror_gap,
                        "spectrum_mode": args.spectrum_mode,
                        "showfreqs_mode": args.showfreqs_mode,
                        "showfreqs_ascale": args.showfreqs_ascale,
                        "showfreqs_fscale": args.showfreqs_fscale,
                        "showfreqs_winfunc": args.showfreqs_winfunc,
                        "showfreqs_overlap": args.showfreqs_overlap,
                        "showfreqs_channels": args.showfreqs_channels,
                        "showvolume_mode": args.showvolume_mode,
                        "showvolume_orientation": args.showvolume_orientation,
                        "showvolume_scale": args.showvolume_scale,
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
                    "vectorscope_scale": args.vectorscope_scale,
                    "vectorscope_zoom": args.vectorscope_zoom,
                    "vectorscope_trails": args.vectorscope_trails,
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
                    "showvolume_mode": args.showvolume_mode,
                    "showvolume_orientation": args.showvolume_orientation,
                    "showvolume_scale": args.showvolume_scale,
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

    # Handle visualizer-config save/load
    if args.visualizer_config:
        preset_path = args.visualizer_config
        if os.path.exists(preset_path):
            # Load preset
            import json as json_mod

            try:
                with open(preset_path) as preset_file:
                    preset = json_mod.load(preset_file)
                # Apply preset values to args
                for key, value in preset.items():
                    if hasattr(args, key):
                        setattr(args, key, value)
                logger.info(f"Loaded preset from {preset_path}")
            except (OSError, json_mod.JSONDecodeError) as e:
                logger.error(f"Failed to load preset: {e}")
        else:
            # Save current args as preset
            preset = {}
            for key in dir(args):
                if key.startswith("_"):
                    continue
                value = getattr(args, key)
                if (
                    value is not None
                    and value != getattr(parser.get_default(key), "__default__", None)
                    if hasattr(parser.get_default(key), "__default__")
                    else True
                ):
                    # Skip non-serializable and default values
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        preset[key] = value
            with open(preset_path, "w") as preset_file:
                json_mod.dump(preset, preset_file, indent=2)
            logger.info(f"Saved preset to {preset_path}")
        return

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
            "albumart_position": args.albumart_position,
            "albumart_glow_intensity": args.albumart_glow_intensity,
            "albumart_fit": args.albumart_fit,
            "albumart_blur": args.albumart_blur,
            "waveform_mode": args.waveform_mode,
            "waveform_splits": args.waveform_splits,
            "waveform_frame": args.waveform_frame,
            "vectorscope_mode": args.vectorscope_mode,
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
            "showvolume_mode": args.showvolume_mode,
            "showvolume_orientation": args.showvolume_orientation,
            "showvolume_scale": args.showvolume_scale,
            "retry": args.retry,
        },
    )


if __name__ == "__main__":
    main()
