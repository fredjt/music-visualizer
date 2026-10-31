"""
Oscilloscope Visualizer Plugin

Time-domain waveform on a grid with persistence (afterglow). Renders the
audio with showwaves (a rolling scope trace, distinct from the `waveform`
mode which ships plain scrolling showwaves without a grid or persistence)
and layers the same peak-hold chain used by `peakbars`
(utils.build_peak_hold_chain) so recent trace positions fade out over
--oscilloscope-persist seconds instead of vanishing.

This plugin is written strictly against the v2.0.0 plugin API (schema +
build_filter only, no base-class hooks) and doubles as a reference
example for the plugin development docs.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser
from .utils import build_peak_hold_chain

# Valid values for showwaves' scale option
OSCILLOSCOPE_SCALES = ("lin", "sqrt", "cbrt", "log", "dbl", "pwr")

# Subtle dark-gray graticule (0xRRGGBB)
_GRID_COLOR = "0x333333"


class OscilloscopePlugin(VisualizerPlugin):
    """
    Time-domain oscilloscope with grid and trace persistence.

    Shows the raw waveform as a rolling point-to-point trace on a dark
    graticule. Positions the trace has recently occupied remain visible
    as a fading afterglow for --oscilloscope-persist seconds.
    """

    metadata = PluginMetadata(
        name="oscilloscope",
        display_name="Oscilloscope",
        description="Time-domain waveform on a grid with persistence/afterglow",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📈",
        category="waveform",
    )

    options = [
        PluginOption(
            "oscilloscope-persist",
            float,
            0.5,
            "Seconds of trace persistence/afterglow (0.0 disables)",
            range=(0.0, 2.0),
        ),
        PluginOption(
            "oscilloscope-scale",
            str,
            "cbrt",
            "Amplitude scale (lin, sqrt, cbrt, log, dbl, pwr)",
            choices=list(OSCILLOSCOPE_SCALES),
        ),
        PluginOption(
            "oscilloscope-grid",
            float,
            0.25,
            "Grid line spacing as a fraction of frame size; 0.0 disables the grid",
            range=(0.0, 1.0),
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
        persist = float(options.get("oscilloscope-persist", 0.5))
        scale = options.get("oscilloscope-scale", "cbrt")
        if scale not in OSCILLOSCOPE_SCALES:
            scale = "cbrt"
        grid = float(options.get("oscilloscope-grid", 0.25))

        parser = ColorParser(colors)
        # Named form (e.g. 'cyan') where possible — nicer in --dry-run output
        pipe = parser.as_pipe_colors()
        trace_color = pipe.split("|")[0] if pipe else "white"

        scope = (
            f"[{audio_index}:a] showwaves=size={width}x{height}"
            f":mode=p2p:scale={scale}:rate={fps}:colors={trace_color}"
        )

        # Tail filters applied after the trace (and the persistence chain):
        # graticule on top — a static grid is a fixed point of the max
        # operation, so it is unaffected by persistence — then the final
        # pixel format.
        tail: list[str] = []
        if grid > 0:
            gw = max(1, int(width * grid))
            gh = max(1, int(height * grid))
            tail.append(f"drawgrid=w={gw}:h={gh}:color={_GRID_COLOR}:t=1")
        tail.append("format=yuv420p[viz]")
        tail_str = ",".join(tail)

        # Persistence: keep the most recent quarter of the window at full
        # brightness, fade the rest (same chain as peakbars, on the trace).
        # Frame counts are computed here so short persists keep their
        # hold/decay proportion instead of inflating to a full-second hold.
        if persist > 0:
            persist_f = int(round(persist * fps))
            if persist_f >= 1:
                hold_f = max(1, int(round(persist_f * 0.25)))
                decay_f = persist_f - hold_f
                graph, out_label = build_peak_hold_chain(
                    "os_src", fps, hold_f / fps, decay_f / fps, "os"
                )
                if graph is not None:
                    # The base class composes the final [out] by overlaying
                    # [viz] on the background input.
                    return f"{scope}[os_src]; {graph}; [{out_label}]{tail_str}"

        return f"{scope},{tail_str}"
