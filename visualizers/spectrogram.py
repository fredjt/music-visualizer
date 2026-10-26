"""
Spectrogram Visualizer Plugin

Displays a scrolling spectrogram (waterfall) showing frequency history over time.
Unlike the spectrum mode which shows current frequencies, this shows a historical
view with older data scrolling downward.
"""

from .base import VisualizerPlugin, PluginMetadata


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

    def build_filter(self, width: int, height: int, fps: int,
                     audio_index: int = 0, video_index: int = 1) -> str:
        # Use a very high overlap to create the waterfall effect
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color=intensity:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=rscroll"
            f":fps={fps}:overlap=0.95,format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
