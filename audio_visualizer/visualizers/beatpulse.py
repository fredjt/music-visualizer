"""
Beatpulse Visualizer Plugin

An onset-reactive radial pulse: a ring that brightens and spreads with
broadband audio energy, then decays. Built strictly against the v2
plugin API and on the existing filter utilities (showvolume for the
level, utils.build_peak_hold_chain for the hold/decay) - no new DSP.

Graph pipeline (all intermediate labels namespaced 'bp_'):
  audio -> lowpass -> showvolume (1x1 level frame) -> full-size flat
  level -> multiplied with a static radial profile (geq) ->
  peak-hold chain -> tinted (colorchannelmixer) -> alphamerge so the
  pulse carries alpha; the base class overlays it on the background.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser
from .utils import build_peak_hold_chain

# Level gain: showvolume's PEAK reads ~130 at full-scale input, so a
# gain of ~2 reaches full brightness at moderate music levels.
_LEVEL_GAIN = 4.0
# Fixed hold/decay for the pulse (onset-reactive feel); the option
# surface is intensity/thickness/color per the spec.
_HOLD_S = 0.05
_DECAY_S = 0.35


class BeatpulsePlugin(VisualizerPlugin):
    """
    Radial pulse ring that expands with broadband energy.

    The audio's peak level drives a radial gradient (bright core fading
    to the edges); higher level lights a larger radius, and the
    existing peak-hold chain holds each onset briefly before it decays.
    """

    metadata = PluginMetadata(
        name="beatpulse",
        display_name="Beat Pulse",
        description="Onset-reactive radial pulse ring driven by broadband energy",
        author="Audio Visualizer",
        version="1.0.0",
        icon="\U0001f4ac",
        category="meter",
    )

    options = [
        PluginOption(
            "beatpulse-intensity",
            float,
            1.0,
            "Pulse size multiplier (0.2-2.0)",
            range=(0.2, 2.0),
        ),
        PluginOption(
            "beatpulse-thickness",
            float,
            1.0,
            "Radial falloff exponent: low = thin core, high = broad ring (0.2-3.0)",
            range=(0.2, 3.0),
        ),
        PluginOption(
            "beatpulse-color",
            str,
            "cyan",
            "Pulse color (named color or hex)",
        ),
    ]

    def build_filter(self, width, height, fps, options, audio_index=0,
                     video_index=1, colors=None, bg_color=None, args=None,
                     **kwargs):
        try:
            cr, cg, cb = ColorParser(options["beatpulse-color"]).as_rgb_tuple()
        except (ValueError, IndexError):
            raise ValueError(
                f"Invalid beatpulse-color: {options['beatpulse-color']!r}"
            )
        intensity = options["beatpulse-intensity"]
        thickness = options["beatpulse-thickness"]

        # 1. Broadband level: lowpassed audio -> 1x1 gray frame (0..255)
        level = (
            f"[{audio_index}:a] lowpass=f=120,"
            f"showvolume=w=80:h=1:o=1:b=0:t=0:v=0:f=0:c='PEAK*255*65793',"
            f"format=gray,scale=1x1 [bp_lv1]"
        )
        # 2. Fan the level out: both branches are finite (audio-length),
        #    which keeps the downstream blend from waiting on an infinite
        #    source
        fan = "[bp_lv1] split=2 [bp_lva] [bp_lvb]"
        # 3. Full-size flat level frame, boosted to full brightness
        flat = (
            f"[bp_lva] scale={width}x{height}:flags=neighbor,"
            f"lutyuv=y='clip(val*{_LEVEL_GAIN:.2f},0,255)' [bp_lv]"
        )
        # 4. Static radial profile (geq) re-derived from the level's timing:
        #    255 at the center fading to 0 at radius
        #    R = 0.48 * min(W,H) * intensity
        r_max = 0.48 * min(width, height) * intensity
        cx, cy = width / 2.0, height / 2.0
        profile = (
            f"[bp_lvb] scale={width}x{height}:flags=neighbor,format=gray,"
            f"geq=lum='255*clip(1-hypot(X-{cx:.1f},Y-{cy:.1f})/"
            f"({r_max + 0.5:.1f}),0,1)^{thickness:.2f}' [bp_prof]"
        )
        # 4. Level * profile: the lit radius grows with the level
        mul = "[bp_prof][bp_lv] blend=all_mode=multiply [bp_mul]"
        # 5. Hold each onset briefly, then decay (existing utility)
        hold_graph, ph_out = build_peak_hold_chain(
            "bp_mul", fps, _HOLD_S, _DECAY_S, "bp"
        )
        hold = f"{hold_graph} " if hold_graph else ""
        # 6. Tint + alpha: RGB = profile * color, alpha = profile level
        #    (split first: each pad may be consumed exactly once)
        split_ = f"[{ph_out}] split=2 [bp_pha] [bp_phb]"
        tint = (
            f"[bp_pha] format=rgb24,"
            f"colorchannelmixer=rr={cr / 255:.4f}:gg={cg / 255:.4f}:"
            f"bb={cb / 255:.4f},format=rgba [bp_rgb]"
        )
        final = "[bp_rgb][bp_phb] alphamerge [viz]"
        return "; ".join(
            [level, fan, flat, profile, mul, hold, split_, tint, final]
        ).strip()
