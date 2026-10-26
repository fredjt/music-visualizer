"""
Color Spectrum Visualizer Plugin

Displays a colorful frequency spectrum with vertical bars that scroll
from right to left. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, VisualizerPlugin


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
            color_list = [c.strip() for c in colors.split(",")]
            if len(color_list) >= 2:
                # Create colormapping mode with custom colors
                color_mapping = f":colormapping={','.join(color_list)}"
                mode = "colormapping"
            else:
                mode = "intensity"
        else:
            mode = "intensity"

        return (
            f"[{audio_index}:a] showspectrum=mode={mode}:color=intensity:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.8{color_mapping},format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
