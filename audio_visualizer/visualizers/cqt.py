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
        cqt_gamma: float = 3.0,
        cqt_basefreq: float = 20.0,
        cqt_endfreq: float = 20495.0,
        cqt_attack: float = 0.0,
        cqt_timeclamp: float = 0.17,
        **kwargs,
    ) -> str:
        # Build color scheme from custom colors if provided
        if colors:
            parser = ColorParser(colors)
            if parser.count >= 2:
                # Use hex colors to build a color scheme string
                hex_colors = parser.as_hex_list()
                # Convert hex to a cscheme-like string (R|G|B|R|G|B|...)
                color_parts = []
                for hex_c in hex_colors[:6]:
                    r = int(hex_c[0:2], 16) / 255.0
                    g = int(hex_c[2:4], 16) / 255.0
                    b = int(hex_c[4:6], 16) / 255.0
                    color_parts.extend([str(r), str(g), str(b)])
                cscheme = "|".join(color_parts)
            else:
                cscheme = "1|0.5|0|0|0.5|1"
        else:
            cscheme = "1|0.5|0|0|0.5|1"

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
            f":fullhd=false"
            f",format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.2[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
