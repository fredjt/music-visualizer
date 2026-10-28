"""
CQT (Constant Q Transform) Visualizer Plugin

Displays a music-theory-friendly frequency spectrum using constant Q transform.
Unlike linear FFT-based spectrum, CQT uses logarithmic frequency spacing,
making it ideal for musical content where octaves and semitones matter.

Uses ffmpeg's showcqt filter.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


class CQTPlugin(VisualizerPlugin):
    """
    Constant Q Transform (CQT) frequency visualization.

    Shows audio frequencies using logarithmic spacing (like musical notes),
    with a sonogram/waterfall effect. Ideal for musical content.
    """

    metadata = PluginMetadata(
        name="cqt",
        display_name="CQT Spectrum",
        description="Music-theory-friendly CQT spectrum with logarithmic frequency spacing",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🎼",
    )

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
        bg_color: str | None = None,
        cqt_gamma: float = 3.0,
        cqt_basefreq: float = 20.0,
        cqt_endfreq: float = 20495.0,
        cqt_attack: float = 0.0,
        cqt_timeclamp: float = 0.17,
        **kwargs,
    ) -> str:
        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        cscheme = parser.as_cqt_scheme()

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.2"
        bg_filter += "[bg]; "

        return (
            f"[{audio_index}:a] showcqt=size={width}x{height}"
            f":rate={fps}"
            f":gamma={cqt_gamma:.1f}"
            f":basefreq={cqt_basefreq:.1f}"
            f":endfreq={cqt_endfreq:.1f}"
            f":attack={cqt_attack:.1f}"
            f":tc={cqt_timeclamp:.3f}"
            f":cscheme={cscheme}"
            f":axis=true"
            f":text=true"
            f",format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
