"""
Showvolume Visualizer Plugin

Displays a reactive volume meter visualization using ffmpeg's showvolume filter.
Shows the audio volume level over time with configurable orientation and mode.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .utils import build_background, compose_output


class ShowvolumePlugin(VisualizerPlugin):
    """
    Reactive volume meter visualization.

    Uses ffmpeg's showvolume filter to display audio volume levels.
    Shows peak or RMS volume with configurable orientation.
    """

    metadata = PluginMetadata(
        name="showvolume",
        display_name="Volume Meter",
        description="Reactive volume meter visualization (peak or RMS)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📊",
        category="meter",
    )

    options = [
        PluginOption(
            "showvolume-mode",
            str,
            "peak",
            "Volume mode (peak, rms)",
            choices=["peak", "rms"],
        ),
        PluginOption(
            "showvolume-orientation",
            str,
            "h",
            "Orientation (h, v)",
            choices=["h", "v"],
        ),
        PluginOption(
            "showvolume-scale",
            str,
            "lin",
            "Display scale (lin, log)",
            choices=["lin", "log"],
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
        showvolume_mode = options.get("showvolume-mode", "peak")
        showvolume_orientation = options.get("showvolume-orientation", "h")
        showvolume_scale = options.get("showvolume-scale", "lin")

        # Map mode to ffmpeg value
        mode_map = {"peak": 0, "rms": 1}
        mode = mode_map.get(showvolume_mode, 0)

        # Map orientation to ffmpeg value
        orientation_map = {"h": 0, "v": 1}
        orientation = orientation_map.get(showvolume_orientation, 0)

        # Map scale to ffmpeg value
        scale_map = {"lin": 0, "log": 1}
        scale = scale_map.get(showvolume_scale, 0)

        # Background
        bg_filter = build_background(video_index, bg_color)

        viz_filter = (
            f"[{audio_index}:a] showvolume=w={width}:h={height}"
            f":rate={fps}"
            f":m={mode}"
            f":o={orientation}"
            f":ds={scale}"
            f",format=yuv420p[viz]; "
        )
        return compose_output(viz_filter, bg_filter)
