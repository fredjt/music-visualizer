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
        description="Symmetrical spectrum with configurable mirror axis (x, y, or xy)",
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
        mirror_axis: str = "y",
        **kwargs,
    ) -> str:
        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Build background source
        if bg_color:
            bg_src = f"color=c={bg_color}:s={width}x{height * 2},format=yuv420p[bg]"
        else:
            bg_src = (
                f"nullsrc=size={width}x{height * 2},format=yuv420p,colorchannelmixer=aa=0.3[bg]"
            )

        # Select flip operation based on mirror axis
        if mirror_axis == "x":
            flip_op = "hflip"
        elif mirror_axis == "xy":
            flip_op = "hflip,vflip"
        else:  # default "y"
            flip_op = "vflip"

        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.7{color_mapping},format=yuv420p[spectrum]; "
            f"[spectrum] split=2[top_copy][flip_src]; "
            f"[flip_src] {flip_op},scale={width}x{height}[flipped]; "
            # Stack original on top, flipped on bottom, scale to target
            f"{bg_src}; "
            f"[bg][top_copy] overlay=shortest=1:format=auto[top]; "
            f"[top][flipped] overlay=shortest=1:y={height}:format=auto[mirrored]; "
            f"[mirrored] format=yuv420p,scale={width}x{height}[out]"
        )
