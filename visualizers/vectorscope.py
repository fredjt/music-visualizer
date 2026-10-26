"""
Vectorscope Visualizer Plugin

Displays a psychedelic circular visualization of the audio signal.
Uses ffmpeg's avectorscope filter to create Lissajous patterns.
"""

from .base import VisualizerPlugin, PluginMetadata


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

    def build_filter(self, width: int, height: int, fps: int,
                     audio_index: int = 0, video_index: int = 1) -> str:
        return (
            f"[{audio_index}:a] avectorscope=size={width}x{height}:draw=aaline"
            f":scale=cbrt:zoom=1.5:mirror=xy:rf=30:gf=20:bf=10"
            f":rate={fps},format=yuv420p[viz]"
        )

    def build_command(self, args: dict) -> list:
        """
        Override to handle vectorscope's unique audio mapping.

        Vectorscope doesn't need a background video input and needs
        explicit audio remapping.
        """
        filter_complex = self.build_filter(
            args["width"], args["height"], args["fps"]
        )

        cmd = ["ffmpeg", "-y", "-i", args["input"]]
        # Vectorscope doesn't need a black background input
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[viz]", "-map", "0:a?"])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", args.get("preset", "medium"),
            "-crf", str(args.get("crf", 23)),
            "-pix_fmt", "yuv420p",
            "-shortest",
            args["output"],
        ])

        return cmd
