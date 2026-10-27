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
        bg_color: str | None = None,
        waveform_mode: str = "line",
        waveform_splits: bool = False,
        waveform_frame: int = 0,
        vectorscope_mode: str = "lissajous",
        vectorscope_draw: str = "aaline",
        vectorscope_scale: str = "cbrt",
        vectorscope_zoom: float = 1.0,
        vectorscope_trails: int = 100,
        cqt_gamma: float = 3.0,
        cqt_basefreq: float = 20.0,
        cqt_endfreq: float = 20495.0,
        cqt_attack: float = 0.0,
        cqt_timeclamp: float = 0.17,
        **kwargs,
    ) -> str:
        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.5{color_mapping},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
