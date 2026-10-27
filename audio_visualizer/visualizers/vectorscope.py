"""
Vectorscope Visualizer Plugin

Displays a psychedelic circular visualization of the audio signal.
Uses ffmpeg's avectorscope filter to create Lissajous patterns.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser

# Valid vectorscope modes
VECTOSCOPE_MODES = ("lissajous", "lissajous_xy", "polar")

# Valid draw modes
VECTOSCOPE_DRAW_MODES = ("dot", "line", "aaline")

# Valid scale modes
VECTOSCOPE_SCALE_MODES = ("lin", "sqrt", "cbrt", "log")


class VectorscopePlugin(VisualizerPlugin):
    """
    Psychedelic circular vectorscope visualization.

    Creates a circular Lissajous pattern from the audio signal.
    Works best with stereo audio - mono signals produce simpler patterns.
    The circle rotates and morphs based on the audio content.
    """

    metadata = PluginMetadata(
        name="vectorscope",
        display_name="Psychedelic Vectorscope",
        description="Psychedelic circular Lissajous pattern visualization",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🌀",
    )

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
        vectorscope_mode: str | None = None,
        vectorscope_draw: str | None = None,
        vectorscope_scale: str | None = None,
        vectorscope_zoom: float = 1.0,
        vectorscope_trails: int = 100,
        **kwargs,
    ) -> str:
        # Validate mode
        if vectorscope_mode not in VECTOSCOPE_MODES:
            vectorscope_mode = "lissajous"

        # Validate draw mode
        if vectorscope_draw not in VECTOSCOPE_DRAW_MODES:
            vectorscope_draw = "aaline"

        # Validate scale mode
        if vectorscope_scale not in VECTOSCOPE_SCALE_MODES:
            vectorscope_scale = "cbrt"

        # Clamp zoom
        vectorscope_zoom = max(0.1, min(10.0, float(vectorscope_zoom)))

        # Convert trails to fade values (higher trails = lower fade)
        # trails 1-255 maps to fade 254-0
        fade = max(0, min(255, 255 - vectorscope_trails))

        # Use custom RGB values if colors provided, otherwise defaults
        if colors:
            parser = ColorParser(colors)
            r, g, b = parser.as_vectorscope_params(default_r=30, default_g=20, default_b=10)
        else:
            r, g, b = 30, 20, 10

        return (
            f"[{audio_index}:a] avectorscope=size={width}x{height}"
            f":mode={vectorscope_mode}"
            f":draw={vectorscope_draw}"
            f":scale={vectorscope_scale}"
            f":zoom={vectorscope_zoom:.1f}"
            f":mirror=xy"
            f":rf={r}:gf={g}:bf={b}"
            f":af={fade}"
            f":rate={fps},format=yuv420p[viz]"
        )

    def build_command(self, args: dict) -> list:
        """
        Override to handle vectorscope's unique audio mapping.

        Vectorscope doesn't need a background video input and needs
        explicit audio remapping.
        """
        filter_complex = self.build_filter(
            args["width"],
            args["height"],
            args["fps"],
            colors=args.get("colors"),
            vectorscope_mode=args.get("vectorscope_mode"),
            vectorscope_draw=args.get("vectorscope_draw"),
            vectorscope_scale=args.get("vectorscope_scale"),
            vectorscope_zoom=args.get("vectorscope_zoom", 1.0),
            vectorscope_trails=args.get("vectorscope_trails", 100),
        )

        cmd = ["ffmpeg", "-y", "-i", args["input"]]
        # Vectorscope doesn't need a black background input
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[viz]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        codec_settings = self._get_codec_settings(fmt, args, accel)

        cmd.extend(codec_settings)
        cmd.extend(["-shortest", args["output"]])

        return cmd
