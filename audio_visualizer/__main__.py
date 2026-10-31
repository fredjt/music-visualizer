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

from audio_visualizer.config import (
    COLOR_THEMES,
    RESOLUTION_PRESETS,
    get_config_path,
    load_config,
    merge_config,
    save_config,
    validate_config,
)
from audio_visualizer.core import (
    OUTPUT_TEMPLATE_DEFAULT,
    _process_batch,
    build_args_dict,
    check_output_template,
    discover_batch_files,
    list_plugins,
    mode_label,
    render_output_template,
    resolve_mode_classes,
    run_visualizer,
)
from audio_visualizer.logging_config import (
    DEBUG,
    ERROR,
    attach_file_handler,
    logger,
    set_level,
)
from audio_visualizer.visualizers._composite import (
    COMPOSE_LAYOUTS,
    COMPOSE_SCALES,
    CompositeVisualizer,
)
from audio_visualizer.visualizers.registry import PLUGIN_PATH_ENV, PluginRegistry


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


def get_package_version() -> str:
    """Package version from installed metadata, or 'unknown' if unavailable."""
    try:
        from importlib.metadata import version

        return version("audio-visualizer")
    except Exception:
        return "unknown"


def get_ffmpeg_version() -> str:
    """First line of `ffmpeg -version`, or '' when ffmpeg is unavailable."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.split("\n", 1)[0].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def print_version_info() -> None:
    """Print package and ffmpeg versions (``--version``)."""
    print(f"audio-visualizer {get_package_version()}")
    ffmpeg_version = get_ffmpeg_version()
    print(f"ffmpeg: {ffmpeg_version}" if ffmpeg_version else "ffmpeg: not found")


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
    # Sort by category, then name, so related plugins are grouped together
    for name, plugin_cls in sorted(
        registry.get_all().items(),
        key=lambda item: (item[1].get_metadata().category, item[0]),
    ):
        meta = plugin_cls.get_metadata()
        options = plugin_cls.get_options()

        if not options:
            continue

        group = parser.add_argument_group(f"[{meta.category}] {meta.display_name} options")

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


def apply_aspect_ratio(resolution: str, aspect_ratio: str | None) -> str | None:
    """
    Recompute a WxH resolution for a given aspect ratio.

    Keeps the base width and adjusts the height (kept even for yuv420p
    compatibility). Returns None if the inputs are not parseable (the
    resolution is then left untouched and validated downstream).

    Args:
        resolution: Base resolution string, e.g. "1280x720".
        aspect_ratio: Aspect ratio string, e.g. "16:9". None means no change.

    Returns:
        New resolution string ("WxH"), or None if it could not be computed.
    """
    if not aspect_ratio:
        return None
    try:
        base_w = int(resolution.split("x")[0])
        ratio_w, ratio_h = (int(x) for x in aspect_ratio.split(":"))
        if base_w <= 0 or ratio_w <= 0 or ratio_h < 0:
            return None
        new_h = (base_w * ratio_h) // ratio_w
        return f"{base_w}x{new_h + new_h % 2}"
    except (ValueError, IndexError):
        return None


def resolve_resolution(resolution: str) -> str:
    """
    Expand a 16:9 preset (e.g. "1080p") to a WxH string.

    WxH strings pass through unchanged; input that matches neither a
    preset nor WxH is left untouched for downstream validation.
    """
    key = resolution.strip().lower()
    return RESOLUTION_PRESETS.get(key, resolution)


# Named-color to ANSI 256-color swatch codes for --list-themes
THEME_SWATCH_COLORS = {
    "red": 196,
    "orange": 208,
    "yellow": 226,
    "lime": 46,
    "green": 34,
    "teal": 36,
    "cyan": 51,
    "blue": 21,
    "purple": 92,
    "magenta": 207,
    "gray": 245,
    "white": 231,
}


def list_themes() -> None:
    """
    Print available color themes.

    Colors are rendered as ANSI swatches when stdout is a tty, as a
    plain comma-separated list otherwise (so piped output stays clean).
    """
    use_color = sys.stdout.isatty()
    print("Available color themes (use --theme NAME):")
    for name, colors in COLOR_THEMES.items():
        palette = [c.strip() for c in colors.split(",")]
        if use_color:
            rendered = "  ".join(
                f"\033[38;5;{THEME_SWATCH_COLORS.get(c, 250)}m\u2588\u2588\u2588\033[0m {c}"
                for c in palette
            )
        else:
            rendered = ", ".join(palette)
        print(f"  {name:<8} {rendered}")


def _plugin_paths_from_env() -> list[str]:
    """External plugin paths from AUDIO_VISUALIZER_PLUGIN_PATH."""
    env_value = os.environ.get(PLUGIN_PATH_ENV, "")
    return [p for p in env_value.split(os.pathsep) if p]


def _build_registry(plugin_paths: list[str]) -> PluginRegistry:
    """Build a plugin registry that includes the given external plugin paths."""
    registry = PluginRegistry(plugin_paths=list(plugin_paths) + _plugin_paths_from_env())
    registry.load_all()
    return registry


def build_parser(registry: PluginRegistry) -> argparse.ArgumentParser:
    """Build the full CLI parser.

    Global flags are declared explicitly; plugin-specific flags are
    auto-generated from plugin option schemas (build_plugin_args).
    Kept separate from main() so tests can inspect the generated flags.
    """
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
  peakbars          Vertical bars with persistent peaks (hold + decay)
  oscilloscope      Time-domain scope with grid and trace persistence

Plugin Management:
  --list-plugins          List all available visualizer plugins
  --install-plugin FILE   Install a plugin from a Python file
  --plugin-path PATH      Load external plugin .py file(s)/dir(s) (repeatable)

External plugins are also discovered from installed distributions that
register the 'audio-visualizer.plugins' entry-point group.

Examples:
  %(prog)s song.mp3
  %(prog)s song.mp3 --mode waveform
  %(prog)s song.mp3 --mode spectrum waveform   # compose two visualizers
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
        "--mode",
        nargs="+",
        default=["spectrum"],
        help=(
            "Visualization mode/plugin name(s); 2+ are composed into one frame "
            "(default: spectrum); combos like 'spectrum+waveform' also work"
        ),
    )
    parser.add_argument(
        "--compose",
        choices=list(COMPOSE_LAYOUTS),
        default="hstack",
        help="Layout for multi-mode composites (default: hstack)",
    )
    parser.add_argument(
        "--compose-scale",
        choices=list(COMPOSE_SCALES),
        default="fill",
        help="Cell scaling for multi-mode composites: fill stretches, fit preserves aspect ratio (default: fill)",
    )
    parser.add_argument(
        "--resolution",
        "-r",
        default="1280x720",
        help=("Output resolution WxH or preset 360p/480p/720p/1080p/1440p/4k (default: 1280x720)"),
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
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        help="Also write log output (debug level) to PATH",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Show debug-level output")
    parser.add_argument(
        "--list-plugins", action="store_true", help="List all available visualizer plugins"
    )
    parser.add_argument(
        "--category",
        choices=registry.get_categories(),
        default=None,
        help="Filter --list-plugins by plugin category",
    )
    parser.add_argument(
        "--install-plugin", metavar="FILE", help="Install a plugin from a Python file"
    )
    parser.add_argument(
        "--plugin-path",
        metavar="PATH",
        action="append",
        default=[],
        help=(
            "Load external plugin(s) from a .py file or directory (repeatable; "
            f"also {PLUGIN_PATH_ENV}, path-separated)"
        ),
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
        "--parallel",
        "-j",
        metavar="N",
        default="1",
        help=(
            "Run N ffmpeg encodes concurrently in batch mode "
            "(default: 1 = sequential; 'auto' = CPU count)"
        ),
    )
    parser.add_argument(
        "--output-template",
        metavar="TEMPLATE",
        default=OUTPUT_TEMPLATE_DEFAULT,
        help=(
            "Batch output filename template with placeholders "
            "{name} {ext} {mode} {width} "
            f"(default: '{OUTPUT_TEMPLATE_DEFAULT}')"
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Batch: also scan subdirectories",
    )
    parser.add_argument(
        "--include",
        metavar="PATTERN",
        action="append",
        default=[],
        help=(
            "Batch: only process files whose path (relative to the batch dir) "
            "matches this glob (repeatable; default: built-in audio extensions)"
        ),
    )
    parser.add_argument(
        "--exclude",
        metavar="PATTERN",
        action="append",
        default=[],
        help="Batch: skip files whose path matches this glob (repeatable)",
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
    # Output container metadata
    parser.add_argument(
        "--title",
        metavar="TEXT",
        default=None,
        help="Set the output video's title (overrides the source file's tag)",
    )
    parser.add_argument(
        "--artist",
        metavar="TEXT",
        default=None,
        help="Set the output video's artist (overrides the source file's tag)",
    )
    parser.add_argument(
        "--album",
        metavar="TEXT",
        default=None,
        help="Set the output video's album (overrides the source file's tag)",
    )
    parser.add_argument(
        "--comment",
        metavar="TEXT",
        default=None,
        help="Set the output video's comment (overrides the source file's tag)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Strip all metadata tags from the output video",
    )

    parser.add_argument("--theme", choices=list(COLOR_THEMES), help="Predefined color theme")
    parser.add_argument(
        "--list-themes", action="store_true", help="List available color themes and exit"
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
        "--json",
        action="store_true",
        help="With --dry-run: print machine-readable JSON instead of text",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package and ffmpeg versions and exit",
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

    return parser


def main():
    # Pre-parse --plugin-path (repeatable) before the full parser exists, so
    # external plugin schemas can contribute auto-generated CLI flags.
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--plugin-path", action="append", default=[])
    pre_args, _ = pre_parser.parse_known_args()

    # Load plugin registry early so we can auto-generate CLI flags from schemas
    registry = _build_registry(pre_args.plugin_path)

    parser = build_parser(registry)
    args = parser.parse_args()

    # Handle --version (no input file or ffmpeg required)
    if args.version:
        print_version_info()
        return

    # Attach the log file before the console level is set, so a
    # --quiet run still tees full debug detail to the file
    if args.log_file:
        try:
            attach_file_handler(args.log_file)
        except OSError as e:
            logger.error(f"Cannot open log file '{args.log_file}': {e}")
            sys.exit(1)

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
        config_path = save_config(args, registry)
        logger.info(f"Configuration saved to: {config_path}")
        return

    # Load configuration and merge with command-line args
    config = load_config(registry)
    args = merge_config(args, config, registry=registry)

    # Expand resolution presets (e.g. 1080p -> 1920x1080); WxH passes through
    args.resolution = resolve_resolution(args.resolution)

    # Apply --aspect-ratio (overrides --resolution: keeps the base width,
    # recomputes the height, and keeps it even for yuv420p compatibility)
    new_resolution = apply_aspect_ratio(args.resolution, getattr(args, "aspect_ratio", None))
    if new_resolution:
        args.resolution = new_resolution

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
        registry = _build_registry(pre_args.plugin_path)
        valid, invalid = validate_plugins(registry)
        display_validation_results(valid, invalid)
        if invalid:
            sys.exit(1)
        return

    # Handle --list-themes flag
    if args.list_themes:
        list_themes()
        return

    # Handle --dry-run flag
    if args.dry_run:
        registry = _build_registry(pre_args.plugin_path)

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

            audio_files = discover_batch_files(
                batch_dir,
                recursive=args.recursive,
                include=args.include,
                exclude=args.exclude,
            )

            if not audio_files:
                logger.error(f"No audio files found in {batch_dir}")
                sys.exit(1)

            mode_classes = resolve_mode_classes(args, registry)
            if len(mode_classes) > 1:
                plugin_cls = CompositeVisualizer
            else:
                plugin_cls = mode_classes[0]

            try:
                resolution = args.resolution.split("x")
                width, height = int(resolution[0]), int(resolution[1])
            except ValueError as e:
                logger.error(f"Invalid resolution '{args.resolution}': {e}")
                sys.exit(1)

            accel = detect_hwaccel(args.accel)

            try:
                check_output_template(args.output_template, args.format, mode_label(args), width)
            except ValueError as e:
                logger.error(f"Invalid --output-template '{args.output_template}': {e}")
                sys.exit(1)

            entries = []
            for audio_file in audio_files:
                base_name = audio_file.stem
                output_name = render_output_template(
                    args.output_template, base_name, args.format, mode_label(args), width
                )
                output_file = os.path.join(output_dir, output_name)
                cmd = plugin_cls().build_command(
                    build_args_dict(
                        args,
                        input=str(audio_file),
                        output=output_file,
                        width=width,
                        height=height,
                        accel=accel,
                        mode_classes=mode_classes,
                    )
                )
                entries.append({"input": str(audio_file), "output": output_file, "command": cmd})

            if args.json:
                payload = {
                    "input_dir": batch_dir,
                    "output_dir": output_dir,
                    "count": len(entries),
                    "mode": mode_label(args),
                    "width": width,
                    "height": height,
                    "fps": args.fps,
                    "preset": args.preset,
                    "crf": args.crf,
                    "format": args.format,
                    "accel": accel,
                    "files": entries,
                }
                print(json.dumps(payload, indent=2))
                return

            logger.info(f"\nDry Run: {len(entries)} file(s) in {batch_dir}")
            logger.info(f"Output directory: {output_dir}")
            logger.info("")
            for entry in entries:
                logger.info(f"\n  Would encode: {os.path.basename(entry['input'])}")
                logger.info(f"    -> {os.path.basename(entry['output'])}")
                logger.info(f"    Command: {' '.join(entry['command'])}")

            logger.info("")
            logger.info(f"Dry run complete: {len(entries)} file(s)")
        else:
            # Dry run for single file mode
            if not args.input:
                logger.error("Input file required for dry run")
                sys.exit(1)

            mode_classes = resolve_mode_classes(args, registry)
            if len(mode_classes) > 1:
                plugin_cls = CompositeVisualizer
            else:
                plugin_cls = mode_classes[0]

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

            accel = detect_hwaccel(args.accel)
            cmd = plugin_cls().build_command(
                build_args_dict(
                    args,
                    input=args.input,
                    output=output_file,
                    width=width,
                    height=height,
                    accel=accel,
                    mode_classes=mode_classes,
                )
            )

            if args.json:
                payload = {
                    "input": args.input,
                    "output": output_file,
                    "mode": mode_label(args),
                    "width": width,
                    "height": height,
                    "fps": args.fps,
                    "preset": args.preset,
                    "crf": args.crf,
                    "format": args.format,
                    "accel": accel,
                    "command": cmd,
                }
                print(json.dumps(payload, indent=2))
                return

            logger.info("\nDry Run")
            logger.info(f"  Input:      {args.input}")
            logger.info(f"  Output:     {output_file}")
            logger.info(f"  Mode:       {mode_label(args)}")
            logger.info(f"  Resolution: {width}x{height}")
            logger.info(f"  FPS:        {args.fps}")
            logger.info(f"  Preset:     {args.preset}")
            logger.info(f"  CRF:        {args.crf}")
            logger.info(f"  Format:     {args.format}")
            logger.info(f"  Acceleration: {args.accel}")

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
    registry = _build_registry(pre_args.plugin_path)

    if args.list_plugins:
        list_plugins(registry, category=args.category, verbose=args.verbose)
        return

    if args.install_plugin:
        if not os.path.exists(args.install_plugin):
            logger.error(f"Plugin file not found: {args.install_plugin}")
            sys.exit(1)
        registry.install_from_file(args.install_plugin)
        # Reload to pick up new plugin
        registry = _build_registry(pre_args.plugin_path)
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

    # Set default output name
    if args.output is None:
        base = os.path.splitext(os.path.basename(args.input))[0]
        args.output = f"{base}_visualizer.{args.format}"

    # Handle visualizer-config save/load
    if args.visualizer_config:
        preset_path = args.visualizer_config
        if os.path.exists(preset_path):
            # Load preset
            try:
                with open(preset_path) as preset_file:
                    preset = json.load(preset_file)
                # Apply preset values to args
                for key, value in preset.items():
                    if hasattr(args, key):
                        setattr(args, key, value)
                logger.info(f"Loaded preset from {preset_path}")
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load preset: {e}")
        else:
            # Save encoding-relevant options as a preset. We deliberately
            # exclude input/output and CLI-management flags so loading a
            # preset later can't clobber the user's current file.
            allowed = {
                "resolution",
                "fps",
                "preset",
                "crf",
                "format",
                "accel",
                "mode",
                "compose",
                "compose_scale",
                "colors",
                "bg_color",
                "border",
                "border_color",
                "border_width",
                "theme",
                "retry",
                "aspect_ratio",
            }
            # Include every plugin option attribute (schema-driven)
            for plugin_cls_entry in registry.get_all().values():
                for opt_name in plugin_cls_entry.get_options():
                    allowed.add(opt_name.replace("-", "_"))
            preset = {}
            for key in sorted(allowed):
                if hasattr(args, key):
                    value = getattr(args, key)
                    if value is not None and (
                        isinstance(value, (str, int, float, bool))
                        or (isinstance(value, list) and all(isinstance(v, str) for v in value))
                    ):
                        preset[key] = value
            with open(preset_path, "w") as preset_file:
                json.dump(preset, preset_file, indent=2)
            logger.info(f"Saved preset to {preset_path}")
        return

    check_ffmpeg()

    run_visualizer(
        plugin_cls,
        build_args_dict(
            args,
            input=args.input,
            output=args.output,
            width=width,
            height=height,
            mode_classes=mode_classes,
        ),
    )


if __name__ == "__main__":
    main()
