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
import re
import subprocess
import sys
import os
from pathlib import Path
from tqdm import tqdm

# Import plugin system
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata
from audio_visualizer.visualizers.registry import PluginRegistry
from audio_visualizer.config import load_config, save_config, merge_config, get_config_path


def check_ffmpeg():
    """Verify ffmpeg is installed and accessible."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"OK  ffmpeg found: {version_line}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    print("ERROR: ffmpeg is required but not found.")
    print("  Install it with: apt install ffmpeg  or  brew install ffmpeg")
    sys.exit(1)


def get_audio_duration(filepath):
    """Get the duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", filepath],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return float(result.stdout.strip())
    return None


def _run_with_progress(cmd: list, duration: float, verbose: bool = False):
    """
    Run ffmpeg with a progress bar and ETA.

    Args:
        cmd: ffmpeg command list
        duration: Expected duration in seconds
        verbose: Whether to show verbose output
    """
    # Create progress bar
    pbar = tqdm(
        total=int(duration),
        desc="Encoding",
        unit="s",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        initial=0,
    )

    # Run ffmpeg and capture stderr
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    # Support multiple time formats from different ffmpeg versions
    time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)|time=(\d+):(\d+):(\d+)")
    last_time = 0

    try:
        for line in process.stderr:
            # Check for time information
            time_match = time_pattern.search(line)
            if time_match:
                # Handle both float and integer seconds
                if time_match.group(3) is not None:
                    # Format: HH:MM:SS.ss
                    hours, minutes, seconds = time_match.group(1), time_match.group(2), time_match.group(3)
                    current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                else:
                    # Format: HH:MM:SS
                    hours, minutes, seconds = time_match.group(4), time_match.group(5), time_match.group(6)
                    current_time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)

                # Update progress bar
                if current_time > last_time:
                    pbar.n = min(int(current_time), int(duration))
                    pbar.refresh()
                    last_time = current_time

            # Show verbose output if enabled
            if verbose and not time_match:
                print(f"  {line.strip()}")

        process.wait()

    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        print("\nCancelled by user")
        pbar.close()
        sys.exit(130)
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")
        pbar.close()
        sys.exit(1)
    finally:
        # Ensure progress bar is closed and completed
        if pbar.n < pbar.total:
            # Complete the progress bar
            pbar.n = pbar.total
            pbar.refresh()
        pbar.close()

    if process.returncode != 0:
        print("ERROR: ffmpeg failed:")
        process.stderr.seek(0)
        stderr = process.stderr.read().strip()
        lines = stderr.split("\n")
        for line in lines[-20:]:
            print(f"  {line}")
        sys.exit(1)


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
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=5
        )
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
            print(f"WARNING: {accel_mode} not available, falling back to software encoding")
            return "sw"

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return "sw"


def run_visualizer(plugin_cls: type[VisualizerPlugin], args: dict):
    """
    Run the visualization pipeline using a plugin.

    Args:
        plugin_cls: The visualizer plugin class to use
        args: Dictionary with keys: input, output, width, height, fps,
              preset, crf, verbose, accel
    """
    input_file = args["input"]
    output_file = args["output"]

    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)

    duration = get_audio_duration(input_file)
    if duration:
        print(f"OK  Audio duration: {duration:.1f}s")

    # Detect hardware acceleration
    accel = detect_hwaccel(args.get("accel", "auto"))

    # Get plugin metadata
    meta = plugin_cls.get_metadata()

    # Build command using the plugin's method
    cmd = plugin_cls().build_command({
        "input": input_file,
        "output": output_file,
        "width": args["width"],
        "height": args["height"],
        "fps": args["fps"],
        "preset": args["preset"],
        "crf": args["crf"],
        "image": args.get("image"),
        "accel": accel,
    })

    # Print info
    print(f"\nGenerating visualizer...")
    print(f"   Plugin:       {meta.icon or ''} {meta.display_name}")
    print(f"   Description:  {meta.description}")
    print(f"   Resolution:   {args['width']}x{args['height']}")
    print(f"   FPS:          {args['fps']}")
    print(f"   Preset:       {args['preset']}")
    print(f"   CRF:          {args['crf']}")
    print(f"   Acceleration: {accel}")

    if args["verbose"]:
        # Rebuild filter to show it
        plugin = plugin_cls()
        fc = plugin.build_filter(args["width"], args["height"], args["fps"])
        print(f"\nFilter complex:")
        for line in fc.split("; "):
            if line.strip():
                print(f"  {line.strip()};")

    print()

    # Run ffmpeg with progress tracking
    if duration and duration > 0:
        _run_with_progress(cmd, duration, args.get("verbose", False))
    else:
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            print("ERROR: ffmpeg failed:")
            stderr = process.stderr.strip()
            lines = stderr.split("\n")
            for line in lines[-20:]:
                print(f"  {line}")
            sys.exit(1)

    # Check output file
    if os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\nOK  Visualizer saved to: {output_file}")
        print(f"     Size: {size_mb:.2f} MB")
    else:
        print(f"ERROR: Output file not created: {output_file}")
        sys.exit(1)


def list_plugins(registry: PluginRegistry):
    """Display all available visualizer plugins."""
    plugins = registry.list_plugins()
    if not plugins:
        print("No plugins found. Run 'python3 audio_visualizer.py --install-plugin <file>' to add one.")
        return

    print(f"\nAvailable Visualizer Plugins ({len(plugins)}):")
    print("=" * 60)
    for p in plugins:
        icon = p.get("icon", "")
        name = p["name"]
        display = p["display_name"]
        desc = p["description"]
        author = f" by {p['author']}" if p.get("author") else ""
        print(f"\n  {icon} {display}")
        print(f"     Name: {name}{author}")
        print(f"     Ver:  {p['version']}")
        print(f"     Desc: {desc}")
    print()


def _process_batch(args, registry):
    """
    Process all audio files in a directory.

    Args:
        args: Parsed command-line arguments
        registry: Plugin registry instance
    """
    batch_dir = args.batch

    if not os.path.isdir(batch_dir):
        print(f"ERROR: Directory not found: {batch_dir}")
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
        print(f"ERROR: No audio files found in {batch_dir}")
        print(f"  Supported formats: {', '.join(sorted(audio_extensions))}")
        sys.exit(1)

    print(f"Found {len(audio_files)} audio file(s) in {batch_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Get plugin class
    plugin_cls = registry.get(args.mode)
    if plugin_cls is None:
        available = ", ".join(registry.list_plugins())
        print(f"ERROR: Unknown mode '{args.mode}'")
        print(f"  Available modes: {available}")
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
        print(f"ERROR: Invalid resolution '{args.resolution}': {e}")
        print("  Use format: WxH (e.g., 1920x1080)")
        sys.exit(1)

    check_ffmpeg()

    # Process each file
    success_count = 0
    fail_count = 0

    with tqdm(total=len(audio_files), desc="Batch") as pbar:
        try:
            for audio_file in audio_files:
                try:
                # Set output filename in output directory
                base_name = audio_file.stem
                output_file = os.path.join(output_dir, f"{base_name}_visualizer.{args.format}")

                # Check if output file exists
                if os.path.exists(output_file) and not args.overwrite:
                    print(f"\nSKIP  {audio_file.name}: Output already exists ({os.path.basename(output_file)})")
                    print(f"      Use --overwrite to replace")
                    fail_count += 1
                    pbar.update(1)
                    continue

                run_visualizer(plugin_cls, {
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
                })
                success_count += 1

            except Exception as e:
                fail_count += 1
                print(f"\nERROR: Failed to process {audio_file.name}: {e}")

            pbar.update(1)

        except KeyboardInterrupt:
            print("\n\nBatch processing cancelled by user")
            pbar.close()
            sys.exit(130)
        finally:
            pbar.close()

    print(f"\nBatch complete: {success_count} succeeded, {fail_count} failed")


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
"""
    )

    parser.add_argument("input", nargs="?", help="Input MP3 (or audio) file")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file (single) or output directory (batch mode)"
    )
    parser.add_argument(
        "--mode", default="spectrum",
        help="Visualization mode/plugin name (default: spectrum)"
    )
    parser.add_argument(
        "--resolution", "-r", default="1280x720",
        help="Output resolution WxH (default: 1280x720)"
    )
    parser.add_argument(
        "--fps", type=int, default=30,
        help="Frame rate (default: 30)"
    )
    parser.add_argument(
        "--preset", choices=[
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ], default="medium",
        help="Encoding preset (default: medium)"
    )
    parser.add_argument(
        "--crf", type=int, default=23, choices=range(0, 52),
        help="Quality (18=lossless, 23=default, 28=max). Lower=better (default: 23)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed filter and command info"
    )
    parser.add_argument(
        "--list-plugins", action="store_true",
        help="List all available visualizer plugins"
    )
    parser.add_argument(
        "--install-plugin", metavar="FILE",
        help="Install a plugin from a Python file"
    )
    parser.add_argument(
        "--image", metavar="FILE",
        help="Image file for image visualizer plugin (album art)"
    )
    parser.add_argument(
        "--format", "-f", default="mp4",
        choices=["mp4", "mkv", "webm", "avi", "mov", "flv"],
        help="Output format (default: mp4)"
    )
    parser.add_argument(
        "--accel", choices=["auto", "nvenc", "qsv", "vaapi", "disabled"],
        default="auto",
        help="Hardware acceleration (default: auto)"
    )
    parser.add_argument(
        "--batch", "-b", metavar="DIRECTORY",
        help="Process all audio files in a directory"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing output files in batch mode"
    )
    parser.add_argument(
        "--colors", metavar="COLORS",
        help="Comma-separated colors for visualizer (e.g., 'blue,green,white')"
    )
    parser.add_argument(
        "--theme", choices=["neon", "sunset", "ocean", "forest", "dark", "light"],
        help="Predefined color theme"
    )
    parser.add_argument(
        "--config", action="store_true",
        help="Show current configuration file path"
    )
    parser.add_argument(
        "--save-config", action="store_true",
        help="Save current options to configuration file"
    )

    args = parser.parse_args()

    # Handle --config flag
    if args.config:
        config_path = get_config_path()
        print(f"Configuration file: {config_path}")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                print(f.read())
        else:
            print("No configuration file found. Run with --save-config to create one.")
        return

    # Handle --save-config flag
    if args.save_config:
        config_path = save_config(args)
        print(f"Configuration saved to: {config_path}")
        return

    # Load configuration and merge with command-line args
    config = load_config()
    args = merge_config(args, config)

    # Initialize plugin registry
    registry = PluginRegistry()
    loaded = registry.load_all()

    if args.list_plugins:
        list_plugins(registry)
        return

    if args.install_plugin:
        if not os.path.exists(args.install_plugin):
            print(f"ERROR: Plugin file not found: {args.install_plugin}")
            sys.exit(1)
        registry.install_from_file(args.install_plugin)
        # Reload to pick up new plugin
        registry = PluginRegistry()
        registry.load_all()
        meta = registry.get_metadata(os.path.splitext(os.path.basename(args.install_plugin))[0])
        if meta:
            print(f"OK  Plugin installed: {meta.display_name}")
            print(f"     Name: {meta.name}")
            print(f"     Run with: --mode {meta.name}")
        else:
            # Try to find by scanning
            for name, cls in registry.get_all().items():
                m = cls.get_metadata()
                if os.path.basename(args.install_plugin).replace(".py", "") in name:
                    print(f"OK  Plugin installed: {m.display_name}")
                    print(f"     Name: {m.name}")
                    print(f"     Run with: --mode {m.name}")
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
        print(f"ERROR: Unknown mode '{args.mode}'")
        print(f"  Available modes: {available}")
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
        print(f"ERROR: Invalid resolution '{args.resolution}': {e}")
        print("  Use format: WxH (e.g., 1920x1080)")
        sys.exit(1)

    # Set default output name
    if args.output is None:
        base = os.path.splitext(os.path.basename(args.input))[0]
        args.output = f"{base}_visualizer.{args.format}"

    check_ffmpeg()


    run_visualizer(plugin_cls, {
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
    })


if __name__ == "__main__":
    main()
