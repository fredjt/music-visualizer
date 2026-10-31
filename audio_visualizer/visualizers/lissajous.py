"""
Lissajous Visualizer Plugin

A band phase portrait: a parametric plot of the low band (X) against
the high band (Y). The audio is split into a lowpassed and a
highpassed copy, merged onto the two channels of a stereo stream, and
plotted with avectorscope in lissajous mode - distinct from
`vectorscope` (raw L/R channels) and `oscilloscope` (single time-domain
waveform).

Written strictly against the v2 plugin API (schema + build_filter only).
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin


class LissajousPlugin(VisualizerPlugin):
    """
    Parametric plot of a low band (X) vs a high band (Y).

    The trail (persistence) is controlled by the avectorscope fade:
    --lissajous-smooth 0.0 draws a crisp point, 1.0 leaves a long
    phosphor-like trail.
    """

    metadata = PluginMetadata(
        name="lissajous",
        display_name="Band Lissajous",
        description="Parametric plot of the low band (X) vs the high band (Y)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="\U0001f9ea",
        category="scope",
    )

    options = [
        PluginOption(
            "lissajous-low-band",
            int,
            300,
            "X channel: lowpass cutoff in Hz (20-2000)",
            range=(20, 2000),
        ),
        PluginOption(
            "lissajous-high-band",
            int,
            3000,
            "Y channel: highpass cutoff in Hz (200-20000)",
            range=(200, 20000),
        ),
        PluginOption(
            "lissajous-smooth",
            float,
            0.7,
            "Trail persistence: 0.0 = crisp point, 1.0 = long trail (0.0-1.0)",
            range=(0.0, 1.0),
        ),
    ]

    def get_inputs(self, args: dict) -> list[list[str]]:
        """
        Lissajous only needs the audio input - avectorscope draws its
        own black background (like vectorscope).
        """
        return [["-i", args["input"]]]

    def build_filter(
        self,
        width,
        height,
        fps,
        options,
        audio_index=0,
        video_index=1,
        colors=None,
        bg_color=None,
        args=None,
        **kwargs,
    ):
        # .get() with fallbacks: validate_plugins probes build_filter with
        # a bare options dict (no defaults filled)
        low = int(options.get("lissajous-low-band") or 300)
        high = int(options.get("lissajous-high-band") or 3000)
        smooth = float(
            options.get("lissajous-smooth") if options.get("lissajous-smooth") is not None else 0.7
        )
        # Fade 0..255: higher keeps the trail longer. 8 = almost no
        # trail (crisp point), 255 = very long persistence.
        fade = int(8 + smooth * (255 - 8))

        split_ = f"[{audio_index}:a] asplit=2 [lj_a] [lj_b]"
        low_ch = f"[lj_a] lowpass=f={low} [lj_l]"
        high_ch = f"[lj_b] highpass=f={high} [lj_h]"
        merge = "[lj_l][lj_h] amerge=inputs=2,aformat=channel_layouts=stereo [lj_2c]"
        scope = (
            f"[lj_2c] avectorscope=mode=lissajous:size={width}x{height}:"
            f"rate={fps}:draw=aaline:scale=cbrt:mirror=xy:zoom=1.0:"
            f"rc=255:gc=255:bc=255:rf={fade}:gf={fade}:bf={fade}:af=0 "
            f"[viz]"
        )
        return "; ".join([split_, low_ch, high_ch, merge, scope]).strip()
