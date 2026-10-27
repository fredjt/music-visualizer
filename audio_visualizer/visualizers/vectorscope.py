"""
Vectorscope Visualizer Plugin

Displays a psychedelic circular visualization of the audio signal.
Uses ffmpeg's avectorscope filter to create Lissajous patterns.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser


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
        waveform_mode: str = "line",
        waveform_splits: bool = False,
        waveform_frame: int = 0,
    ) -> str:
        # Use custom RGB values if colors provided, otherwise defaults
        if colors:
            parser = ColorParser(colors)
            r, g, b = parser.as_vectorscope_params(default_r=30, default_g=20, default_b=10)
        else:
            r, g, b = 30, 20, 10

        return (
            f"[{audio_index}:a] avectorscope=size={width}x{height}:draw=aaline"
            f":scale=cbrt:zoom=1.5:mirror=xy:rf={r}:gf={g}:bf={b}"
            f":rate={fps},format=yuv420p[viz]"
        )

    def build_command(self, args: dict) -> list:
        """
        Override to handle vectorscope's unique audio mapping.

        Vectorscope doesn't need a background video input and needs
        explicit audio remapping.
        """
        filter_complex = self.build_filter(
            args["width"], args["height"], args["fps"], colors=args.get("colors")
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
