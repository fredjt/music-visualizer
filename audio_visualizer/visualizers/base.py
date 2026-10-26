"""
Base Visualizer Plugin

All visualizer plugins must inherit from this class and implement
defined methods. The core system uses these interfaces to build
ffmpeg filter graphs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PluginMetadata:
    """Metadata describing a visualizer plugin."""
    name: str                          # Unique identifier (e.g., 'spectrum')
    display_name: str                  # Human-readable name (e.g., 'Color Spectrum')
    description: str                   # What the visualization does
    author: Optional[str] = None       # Plugin author
    version: str = "1.0.0"            # Plugin version
    icon: Optional[str] = None         # Emoji/icon for display


class VisualizerPlugin(ABC):
    """
    Base class for audio visualizer plugins.

    Every visualizer plugin must:
    1. Inherit from this class
    2. Define a `metadata` class attribute (or property)
    3. Implement `build_filter()` to return the ffmpeg filter_complex string

    The core system handles:
    - Plugin discovery and registration
    - Audio input/output handling
    - ffmpeg execution
    - Error reporting

    Example plugin:
        class MyPlugin(VisualizerPlugin):
            metadata = PluginMetadata(
                name="my_viz",
                display_name="My Visualizer",
                description="Does cool stuff",
            )

            def build_filter(self, width: int, height: int, fps: int,
                             audio_index: int, video_index: int) -> str:
                return f"[{audio_index}:a] myfilter=size={width}x{height}[viz]; ..."
    """

    # Override this with plugin metadata
    metadata: PluginMetadata = None  # type: ignore

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Return the plugin's metadata."""
        if cls.metadata is None:
            raise NotImplementedError(
                f"{cls.__name__} must define a 'metadata' class attribute"
            )
        return cls.metadata

    @abstractmethod
    def build_filter(self, width: int, height: int, fps: int,
                     audio_index: int = 0, video_index: int = 1) -> str:
        """
        Build the ffmpeg filter_complex string for this visualizer.

        Args:
            width: Output video width in pixels
            height: Output video height in pixels
            fps: Frame rate (frames per second)
            audio_index: Index of the audio input stream in ffmpeg command
            video_index: Index of the black background video input

        Returns:
            A complete filter_complex string that produces an '[out]' labeled output.
            The filter should consume audio from [audio_index]:a and optionally
            use [video_index]:v as a background.

        Example return value:
            "[0:a] showspectrum=size=1280x720:scale=log[viz]; "
            "[1:v][viz] overlay=shortest=1[out]"
        """
        pass

    def build_command(self, args: dict) -> list:
        """
        Build the complete ffmpeg command for this plugin.

        Override this to customize the ffmpeg command (e.g., add custom inputs,
        change encoding settings). The default implementation handles the common case.

        Args:
            args: Dictionary with keys:
                - input: Input audio file path
                - output: Output video file path
                - width: Output width
                - height: Output height
                - fps: Frame rate
                - preset: x264 preset
                - crf: Constant Rate Factor

        Returns:
            List of ffmpeg command arguments
        """
        filter_complex = self.build_filter(
            args["width"], args["height"], args["fps"]
        )

        cmd = ["ffmpeg", "-y", "-i", args["input"]]

        # Add black background video source
        cmd.extend([
            "-f", "lavfi",
            "-i", f"color=c=black:s={args['width']}x{args['height']}:r={args['fps']}",
        ])

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[out]", "-map", "0:a?"])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", args.get("preset", "medium"),
            "-crf", str(args.get("crf", 23)),
            "-pix_fmt", "yuv420p",
            "-shortest",
            args["output"],
        ])

        return cmd
