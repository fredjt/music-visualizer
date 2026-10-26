"""
Spectrogram Visualizer Plugin

Displays a scrolling spectrogram (waterfall) showing frequency history over time.
Unlike the spectrum mode which shows current frequencies, this shows a historical
view with older data scrolling downward.
"""

from .base import PluginMetadata, VisualizerPlugin


class SpectrogramPlugin(VisualizerPlugin):
    """
    Scrolling spectrogram / waterfall visualization.

    Shows frequency content over time with a scrolling effect.
    Low frequencies are at the bottom (red/orange), high frequencies
    fade to blue/purple at the top. Older data scrolls downward.
    """

    metadata = PluginMetadata(
        name="spectrogram",
        display_name="Spectrogram Waterfall",
        description="Scrolling spectrogram showing frequency history over time (waterfall view)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🌊",
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
            color_list = [c.strip() for c in colors.split(",")]
            if len(color_list) >= 2:
                color_mapping = f":colormapping={','.join(color_list)}"
                color_mode = "colormapping"

        # Use a very high overlap to create the waterfall effect
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=rscroll"
            f":fps={fps}:overlap=0.95{color_mapping},format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
