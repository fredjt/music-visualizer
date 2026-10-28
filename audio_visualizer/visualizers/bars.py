"""
Bars Visualizer Plugin

Displays a classic bar spectrum with customizable width, spacing,
orientation, and rounded bar tops. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


class BarsPlugin(VisualizerPlugin):
    """
    Classic bar spectrum visualization with custom parameters.

    Shows the frequency spectrum as bars with configurable:
    - bar width/thickness in pixels
    - spacing between bars
    - orientation (horizontal/vertical)
    - rounded bar tops
    """

    metadata = PluginMetadata(
        name="bars",
        display_name="Classic Bars",
        description="Classic bar spectrum with customizable width, spacing, orientation, and rounded tops",
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
        bar_width: int = 0,
        bar_spacing: float = 0.5,
        bar_orientation: str = "horizontal",
        bar_radius: int = 0,
        **kwargs,
    ) -> str:
        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Clamp bar width (0 = use ffmpeg default)
        bar_width = max(0, min(width // 2, int(bar_width)))

        # Clamp bar spacing (0.0 = no gap, 1.0 = maximum gap)
        bar_spacing = max(0.0, min(1.0, float(bar_spacing)))

        # Validate orientation
        if bar_orientation not in ("horizontal", "vertical"):
            bar_orientation = "horizontal"

        # Clamp bar radius
        bar_radius = max(0, min(min(width, height) // 4, int(bar_radius)))

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        # Orientation: horizontal (default) vs vertical
        if bar_orientation == "vertical":
            return (
                f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
                f"size={height}x{width}:scale=log:slide=scroll"
                f":fps={fps}:overlap={bar_spacing}{color_mapping},format=yuv420p[viz]; "
                f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
            )

        # Horizontal bars (default)
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap={bar_spacing}{color_mapping},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
