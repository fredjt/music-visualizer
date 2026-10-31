"""Showfreqs Visualizer Plugin

Uses ffmpeg's showfreqs filter to create a frequency-domain visualization
with labeled frequency bands. Educational and visually distinct.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


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
        category="spectrum",
    )

    options = [
        PluginOption(
            "showfreqs-mode",
            str,
            "bar",
            "Display mode (bar, line, dot)",
            choices=["bar", "line", "dot"],
        ),
        PluginOption(
            "showfreqs-ascale",
            str,
            "log",
            "Amplitude scale (lin, sqrt, cbrt, log)",
            choices=["lin", "sqrt", "cbrt", "log"],
        ),
        PluginOption(
            "showfreqs-fscale",
            str,
            "log",
            "Frequency scale (lin, log, rlog)",
            choices=["lin", "log", "rlog"],
        ),
        PluginOption(
            "showfreqs-winfunc",
            str,
            "hann",
            "Window function (hann, hamming, blackman, etc.)",
            choices=[
                "rect",
                "bartlett",
                "hann",
                "hanning",
                "hamming",
                "blackman",
                "welch",
                "flattop",
                "bharris",
                "bnuttall",
                "bhann",
                "sine",
                "nuttall",
                "lanczos",
                "gauss",
                "tukey",
                "dolph",
                "cauchy",
                "parzen",
                "poisson",
                "bohman",
                "kaiser",
            ],
        ),
        PluginOption(
            "showfreqs-overlap",
            float,
            0.5,
            "Window overlap (0.0-1.0)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "showfreqs-channels",
            str,
            "all",
            "Channels to draw (all, 0, 1, etc.)",
        ),
    ]

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        options: dict,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
        bg_color: str | None = None,
        **kwargs,
    ) -> str:
        # Extract options
        showfreqs_mode = options.get("showfreqs-mode", "bar")
        showfreqs_ascale = options.get("showfreqs-ascale", "log")
        showfreqs_fscale = options.get("showfreqs-fscale", "log")
        showfreqs_winfunc = options.get("showfreqs-winfunc", "hann")
        showfreqs_overlap = options.get("showfreqs-overlap", 0.5)
        showfreqs_channels = options.get("showfreqs-channels", "all")

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

        # Build color string from colors parameter. Theme/--colors values
        # are comma-separated; showfreqs' colors option is pipe-separated,
        # so convert (a raw comma string would break the filtergraph).
        if colors:
            color_str = ColorParser(colors).as_pipe_colors()
        else:
            color_str = "red|green|blue|yellow|orange|lime|pink|magenta|brown"

        # The base class composes the final [out] by overlaying [viz]
        # on the background input.
        return (
            f"[{audio_index}:a] showfreqs=size={width}x{height}:rate={fps}"
            f":mode={mode}"
            f":ascale={ascale}"
            f":fscale={fscale}"
            f":win_func={win_func}"
            f":overlap={overlap:.1f}"
            f":colors={color_str}"
            f":channels={showfreqs_channels}"
            f",format=yuv420p[viz]"
        )
