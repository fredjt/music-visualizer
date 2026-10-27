"""
Waveform Visualizer Plugin

Displays an animated waveform of the audio signal with gradient colors.
Uses ffmpeg's showwaves filter.
"""

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser

# Valid waveform modes
WAVEFORM_MODES = ("point", "line", "p2p", "cline")


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
        bg_color: str | None = None,
        waveform_mode: str | None = None,
        waveform_splits: bool = False,
        waveform_frame: int = 0,
        **kwargs,
    ) -> str:
        # Default mode
        if waveform_mode not in WAVEFORM_MODES:
            waveform_mode = "line"

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        wave_colors = parser.as_waves_colors()

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        # Build filter parameters
        parts = [
            f"[{audio_index}:a] showwaves=size={width}x{height}",
            f"mode={waveform_mode}",
            f"colors={wave_colors}",
            "scale=cbrt",
            f"rate={fps}",
        ]

        if waveform_splits:
            parts.append("split_channels=1")

        if waveform_frame and waveform_frame > 0:
            parts.append(f"n={waveform_frame}")

        filter_str = ":".join(parts)

        return (
            f"{filter_str},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
