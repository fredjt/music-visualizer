"""
Color Spectrum Visualizer Plugin

Displays a colorful frequency spectrum with vertical bars that scroll
from right to left. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


class SpectrumPlugin(VisualizerPlugin):
    """
    Colorful frequency spectrum visualization.

    Shows audio frequencies as colored vertical bars that scroll
    across the screen. Low frequencies are at the bottom (red/orange),
    high frequencies fade to blue/purple at the top.
    """

    metadata = PluginMetadata(
        name="spectrum",
        display_name="Color Spectrum",
        description="Colorful frequency spectrum with vertical bars that scroll across the screen",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🌈",
    )

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
    ) -> str:

        # Build color mapping if custom colors provided
        color_mapping = ""
        if colors:
            parser = ColorParser(colors)
            if parser.count >= 2:
                color_mapping = f":colormapping={parser.as_colormapping()}"
                mode = "colormapping"
            else:
                mode = "intensity"
        else:
            mode = "intensity"

        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.8{color_mapping},format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
