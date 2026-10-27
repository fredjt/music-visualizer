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
        mode, color_mapping = parser.as_spectrum_mode()
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
            f"[{audio_index}:a] showspectrum=mode=separate:color={mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.8{color_mapping},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
