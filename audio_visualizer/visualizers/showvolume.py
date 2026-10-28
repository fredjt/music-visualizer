"""
Showvolume Visualizer Plugin

Displays a reactive volume meter visualization using ffmpeg's showvolume filter.
Shows the audio volume level over time with configurable orientation and mode.
"""

from .base import PluginMetadata, VisualizerPlugin


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
    )

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
        bg_color: str | None = None,
        waveform_mode: str = "line",
        waveform_splits: bool = False,
        waveform_frame: int = 0,
        vectorscope_mode: str = "lissajous",
        vectorscope_draw: str = "aaline",
        vectorscope_scale: str = "cbrt",
        vectorscope_zoom: float = 1.0,
        vectorscope_trails: int = 100,
        cqt_gamma: float = 3.0,
        cqt_basefreq: float = 20.0,
        cqt_endfreq: float = 20495.0,
        cqt_attack: float = 0.0,
        cqt_timeclamp: float = 0.17,
        showvolume_mode: str = "peak",
        showvolume_orientation: str = "h",
        showvolume_scale: str = "lin",
        **kwargs,
    ) -> str:
        # Map mode to ffmpeg value
        mode_map = {"peak": 0, "rms": 1}
        mode = mode_map.get(showvolume_mode, 0)

        # Map orientation to ffmpeg value
        orientation_map = {"h": 0, "v": 1}
        orientation = orientation_map.get(showvolume_orientation, 0)

        # Map scale to ffmpeg value
        scale_map = {"lin": 0, "log": 1}
        scale = scale_map.get(showvolume_scale, 0)

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        return (
            f"[{audio_index}:a] showvolume=w={width}:h={height}"
            f":rate={fps}"
            f":m={mode}"
            f":o={orientation}"
            f":ds={scale}"
            f",format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
