"""
Vectorscope Visualizer Plugin

Displays a psychedelic circular visualization of the audio signal.
Uses ffmpeg\'s avectorscope filter to create Lissajous patterns.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser

# Valid vectorscope modes (map to ffmpeg draw parameter)
VECTOSCOPE_MODES = ("frame", "line", "dot")

# Map user-friendly mode names to ffmpeg draw parameter
VECTOSCOPE_MODE_MAP = {
    "frame": "aaline",  # filled/anti-aliased lines (current default)
    "line": "line",
    "dot": "dot",
}

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
        color_index: int = 0,
        vectorscope_mode: str | None = None,
        vectorscope_scale: str | None = None,
        vectorscope_zoom: float = 1.0,
        vectorscope_trails: int = 100,
        vectorscope_framerate: int = 0,
        vectorscope_border: bool = False,
        vectorscope_border_color: str = "ffffff",
        vectorscope_border_width: int = 2,
        **kwargs,
    ) -> str:
        # Validate and map mode (frame -> aaline for ffmpeg)
        if vectorscope_mode not in VECTOSCOPE_MODES:
            vectorscope_mode = "frame"
        draw_mode = VECTOSCOPE_MODE_MAP[vectorscope_mode]

        # Validate scale mode
        if vectorscope_scale not in VECTOSCOPE_SCALE_MODES:
            vectorscope_scale = "cbrt"

        # Clamp zoom
        vectorscope_zoom = max(0.1, min(10.0, float(vectorscope_zoom)))

        # Clamp trails
        vectorscope_trails = max(0, min(255, int(vectorscope_trails)))

        # Convert trails to fade values (higher trails = lower fade)
        fade = 255 - vectorscope_trails

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        r, g, b = parser.as_vectorscope_params(
            index=color_index, default_r=255, default_g=255, default_b=255
        )

        # Build border if enabled
        border_filter = ""
        if vectorscope_border:
            border_filter = (
                f"[viz]format=rgba,colorchannelmixer=rr=1.0:gg=1.0:bb=1.0:aa=1.0[viz_alpha]; "
                f"color=c={vectorscope_border_color}:s={width}x{height}:r={fps},format=yuva420p[border]; "
                f"[border][viz_alpha]overlay=shortest=1:format=auto[out]"
            )

        # Use custom framerate if provided, otherwise use fps parameter
        rate = vectorscope_framerate if vectorscope_framerate > 0 else fps

        base_filter = (
            f"[{audio_index}:a] avectorscope=size={width}x{height}"
            f":mode=lissajous"
            f":draw={draw_mode}"
            f":scale={vectorscope_scale}"
            f":zoom={vectorscope_zoom:.1f}"
            f":mirror=xy"
            f":rc={r}:gc={g}:bc={b}"
            f":rf={fade}:gf={fade}:bf={fade}"
            f":af={fade}"
            f":rate={rate},format=yuv420p[viz]"
        )

        if border_filter:
            return f"{base_filter}; {border_filter}"
        return f"{base_filter},format=yuv420p[out]"

    def build_command(self, args: dict) -> list:
        """
        Override to handle vectorscope's unique audio mapping.

        Vectorscope doesn\'t need a background video input and needs
        explicit audio remapping.
        """
        filter_complex = self.build_filter(
            args["width"],
            args["height"],
            args["fps"],
            colors=args.get("colors"),
            color_index=args.get("vectorscope_color_index", 0),
            vectorscope_mode=args.get("vectorscope_mode"),
            vectorscope_scale=args.get("vectorscope_scale"),
            vectorscope_zoom=args.get("vectorscope_zoom", 1.0),
            vectorscope_trails=args.get("vectorscope_trails", 100),
            vectorscope_framerate=args.get("vectorscope_framerate", 0),
            vectorscope_border=args.get("vectorscope_border", False),
            vectorscope_border_color=args.get("vectorscope_border_color", "ffffff"),
            vectorscope_border_width=args.get("vectorscope_border_width", 2),
        )

        cmd = ["ffmpeg", "-y", "-i", args["input"]]
        # Vectorscope doesn\'t need a black background input
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[out]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")

        codec_settings = self._get_codec_settings(fmt, args, accel)
        cmd.extend(codec_settings)
        cmd.extend(["-shortest", args["output"]])

        return cmd
