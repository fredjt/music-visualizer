"""
Waveform Visualizer Plugin

Displays an animated waveform of the audio signal with gradient colors.
Uses ffmpeg's showwaves filter.
"""

from .base import PluginMetadata, VisualizerPlugin


class WaveformPlugin(VisualizerPlugin):
    """
    Animated waveform visualization with gradient colors.

    Shows the audio waveform as colored lines that move across
    the screen. Uses red, green, and blue channels for a
    rainbow effect on the waveform.
    """

    metadata = PluginMetadata(
        name="waveform",
        display_name="Gradient Waveform",
        description="Animated waveform display with red/green/blue gradient colors",
        author="Audio Visualizer",
        version="1.0.0",
        icon="〰️",
    )

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
    ) -> str:
        # Use custom colors if provided, otherwise default to red|green|blue
        wave_colors = colors if colors else "red|green|blue"
        return (
            f"[{audio_index}:a] showwaves=size={width}x{height}:mode=line:colors={wave_colors}"
            f":scale=cbrt:rate={fps},format=yuv420p[viz]; "
            f"[{video_index}:v] format=rgba,colorchannelmixer=aa=0.3[bg]; "
            f"[bg][viz] overlay=shortest=1:format=auto [out]"
        )
