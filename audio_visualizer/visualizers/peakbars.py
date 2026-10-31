"""
Peakbars Visualizer Plugin

Vertical frequency bars with persistent peak indicators. The top of each
bar is held at its maximum for a configurable hold time, then decays
exponentially — behavior showspectrum/showfreqs cannot produce on their
own, so this plugin builds a custom filter chain (delayed attenuated taps
+ per-pixel max, see utils.build_peak_hold_chain) on top of showfreqs.

This plugin is written strictly against the v2.0.0 plugin API (schema +
build_filter only, no base-class hooks) and doubles as a reference
example for the plugin development docs.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser
from .utils import build_peak_hold_chain

# Default palette when no theme colors are provided (pipe-separated for
# showfreqs' colors option)
_DEFAULT_COLORS = "red|yellow|green|cyan|blue"


class PeakbarsPlugin(VisualizerPlugin):
    """
    Vertical spectrum bars with peak-hold indicators.

    Renders the frequency spectrum as vertical bars (showfreqs in bar
    mode) and overlays a peak-hold layer: each bar's maximum recent
    height is held at full brightness for --peakbars-hold seconds, then
    fades away over --peakbars-decay seconds.
    """

    metadata = PluginMetadata(
        name="peakbars",
        display_name="Peak-Hold Bars",
        description="Vertical spectrum bars with persistent peaks that hold, then decay",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📶",
        category="spectrum",
    )

    options = [
        PluginOption(
            "peakbars-hold",
            float,
            0.1,
            "Seconds each peak is held at full height (0.0-2.0)",
            range=(0.0, 2.0),
        ),
        PluginOption(
            "peakbars-decay",
            float,
            0.6,
            "Seconds the held peak takes to decay away (0.0-2.0)",
            range=(0.0, 2.0),
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
        hold = float(options.get("peakbars-hold", 0.1))
        decay = float(options.get("peakbars-decay", 0.6))

        parser = ColorParser(colors)
        color_str = parser.as_pipe_colors() if colors else _DEFAULT_COLORS

        showfreqs = (
            f"[{audio_index}:a] showfreqs=size={width}x{height}:rate={fps}"
            f":mode=1:colors={color_str}"
        )

        graph, out_label = build_peak_hold_chain("pb_src", fps, hold, decay, "pb")
        if graph is None:
            # No hold requested: plain bars, no peak layer
            return f"{showfreqs},format=yuv420p[viz]"

        # The base class composes the final [out] by overlaying [viz]
        # on the background input.
        return f"{showfreqs}[pb_src]; {graph}; [{out_label}]format=yuv420p[viz]"
