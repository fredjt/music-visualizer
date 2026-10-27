"""
Bars Visualizer Plugin

Displays a classic horizontal bar spectrum with less overlap
between bars, creating distinct column-like appearance.
Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


class BarsPlugin(VisualizerPlugin):
    """
    Classic horizontal bar spectrum visualization.

    Similar to the standard spectrum but with reduced overlap
    between frequency bars, creating a more distinct column-like
    appearance. Good for seeing individual frequency components.
    """

    metadata = PluginMetadata(
        name="bars",
        display_name="Classic Bars",
        description="Classic horizontal bar spectrum with less overlap (distinct columns)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📊",
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
        color_mode = "intensity"
        if colors:
            parser = ColorParser(colors)
            if parser.count >= 2:
                color_mapping = f":colormapping={parser.as_colormapping()}"
                color_mode = "colormapping"

        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.5{color_mapping},format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
