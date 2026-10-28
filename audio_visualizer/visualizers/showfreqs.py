"""Showfreqs Visualizer Plugin

Uses ffmpeg's showfreqs filter to create a frequency-domain visualization
with labeled frequency bands. Educational and visually distinct.
"""

from .base import PluginMetadata, VisualizerPlugin


class ShowfreqsPlugin(VisualizerPlugin):
    """
    Frequency-domain visualization with labeled bands.

    Uses ffmpeg's showfreqs filter to display audio frequencies
    with support for different display modes, scales, and window functions.
    """

    metadata = PluginMetadata(
        name="showfreqs",
        display_name="Showfreqs",
        description="Frequency-domain visualization with labeled bands (showfreqs filter)",
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
        showfreqs_mode: str = "bar",
        showfreqs_ascale: str = "log",
        showfreqs_fscale: str = "log",
        showfreqs_winfunc: str = "hann",
        showfreqs_overlap: float = 0.5,
        showfreqs_channels: str = "all",
        **kwargs,
    ) -> str:
        # Validate and map mode
        mode_map = {"line": 0, "bar": 1, "dot": 2}
        mode = mode_map.get(showfreqs_mode, 1)

        # Validate and map ascale
        ascale_map = {"lin": 0, "sqrt": 1, "cbrt": 2, "log": 3}
        ascale = ascale_map.get(showfreqs_ascale, 3)

        # Validate and map fscale
        fscale_map = {"lin": 0, "log": 1, "rlog": 2}
        fscale = fscale_map.get(showfreqs_fscale, 1)

        # Validate and map win_func
        win_func_map = {
            "rect": 0,
            "bartlett": 4,
            "hann": 1,
            "hanning": 1,
            "hamming": 2,
            "blackman": 3,
            "flattop": 6,
            "bharris": 7,
            "bnuttall": 8,
            "bhann": 11,
            "sine": 9,
            "nuttall": 10,
            "lanczos": 12,
            "gauss": 13,
            "tukey": 14,
            "dolph": 15,
            "cauchy": 16,
            "parzen": 17,
            "poisson": 18,
            "bohman": 19,
            "kaiser": 20,
        }
        win_func = win_func_map.get(showfreqs_winfunc, 1)

        # Clamp overlap
        overlap = max(0.0, min(1.0, float(showfreqs_overlap)))

        # Build color string from colors parameter
        color_str = colors if colors else "red|green|blue|yellow|orange|lime|pink|magenta|brown"

        return (
            f"[{audio_index}:a] showfreqs=size={width}x{height}:rate={fps}"
            f":mode={mode}"
            f":ascale={ascale}"
            f":fscale={fscale}"
            f":win_func={win_func}"
            f":overlap={overlap:.1f}"
            f":colors={color_str}"
            f":channels={showfreqs_channels}"
            f":format=yuv420p[viz]"
        )
