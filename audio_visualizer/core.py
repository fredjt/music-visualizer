"""
Core functionality for audio visualizer.

Contains the main visualization logic: running ffmpeg with progress tracking,
running the visualization pipeline, listing plugins, and batch processing.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm

# get_audio_duration imported lazily in run_visualizer
from audio_visualizer.visualizers.base import VisualizerPlugin
from audio_visualizer.visualizers.registry import PluginRegistry


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
        for line in stderr_lines[-20:]:
            print(f"  {line.strip()}")
        sys.exit(1)


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
    print("\nGenerating visualizer...")
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
        print(f"   Command: {' '.join(cmd)}")
        fc = plugin.build_filter(
            args["width"], args["height"], args["fps"], colors=args.get("colors")
        )
        print("\nFilter complex:")
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
        print(
            "No plugins found. Run 'python3 audio_visualizer.py --install-plugin <file>' to add one."
        )
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
    # Import here to avoid circular imports
    from audio_visualizer.__main__ import check_ffmpeg, run_visualizer

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
                        print(
                            f"\nSKIP  {audio_file.name}: Output already exists ({os.path.basename(output_file)})"
                        )
                        print("      Use --overwrite to replace")
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
                        },
                    )
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
