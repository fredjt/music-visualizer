"""
Mirrored Spectrum Visualizer Plugin

Displays a symmetrical spectrum with top/bottom reflection.
The original spectrum appears on top, and a vertically-flipped
copy appears below, creating a mirror effect.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


class RadialPlugin(VisualizerPlugin):
    """
    Symmetrical mirrored spectrum visualization.

    Shows the frequency spectrum reflected both upward and downward
    from a center line, creating a symmetrical mirror effect.
    The result is scaled back to the target resolution.
    """

    metadata = PluginMetadata(
        name="radial",
        display_name="Mirrored Spectrum",
        description="Symmetrical spectrum with top/bottom reflection (mirror effect)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🪞",
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
            f":fps={fps}:overlap=0.7{color_mapping},format=yuv420p[spectrum]; "
            f"[spectrum] split=2[top_copy][flip_src]; "
            # Flip spectrum vertically using transpose + hflip
            f"[flip_src] transpose=2,hflip,transpose=1,scale={width}x{height}[flipped]; "
            # Create black canvas twice as tall
            f"nullsrc=size={width}x{height * 2},format=yuv420p,colorchannelmixer=aa=0.3[bg]; "
            # Stack original on top, flipped on bottom, scale to target
            f"[bg][top_copy] overlay=shortest=1:format=auto[top]; "
            f"[top][flipped] overlay=shortest=1:y={height}:format=auto[mirrored]; "
            f"[mirrored] format=yuv420p,scale={width}x{height}[out]"
        )
