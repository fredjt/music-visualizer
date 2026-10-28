"""
Waveform Visualizer Plugin

Displays an animated waveform of the audio signal with gradient colors.
Uses ffmpeg's showwaves filter.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser

# Valid waveform modes for showwaves
WAVEFORM_MODES = ("point", "line", "p2p", "cline", "pict")


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
        category="waveform",
    )

    options = [
        PluginOption(
            "waveform-mode",
            str,
            "line",
            "Waveform display mode (line, point, p2p, cline, pict)",
            choices=list(WAVEFORM_MODES),
        ),
        PluginOption(
            "waveform-splits",
            int,
            1,
            "Number of waveform split channels (1-8)",
            range=(1, 8),
        ),
        PluginOption(
            "waveform-frame",
            int,
            0,
            "Audio samples per frame (0 = default)",
            range=(0, None),
        ),
        PluginOption(
            "waveform-colors-per-channel",
            bool,
            False,
            "Assign different colors per channel",
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
        waveform_mode = options.get("waveform-mode", "line")
        waveform_splits = options.get("waveform-splits", 1)
        waveform_frame = options.get("waveform-frame", 0)
        waveform_colors_per_channel = options.get("waveform-colors-per-channel", False)

        # Default mode
        if waveform_mode not in WAVEFORM_MODES:
            waveform_mode = "line"

        # Clamp splits to valid range
        waveform_splits = max(1, min(8, int(waveform_splits)))

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        # Determine colors to use
        if waveform_colors_per_channel and colors:
            # Assign each channel a different color from the provided palette
            parser = ColorParser(colors)
            # Use each color once per channel (cycle if fewer colors than channels)
            colors_list = parser.resolved
            if colors_list:
                # Build a pipe-separated list: one color per channel
                per_channel = []
                for ch in range(waveform_splits):
                    per_channel.append(colors_list[ch % len(colors_list)])
                wave_colors = "|".join(per_channel)
            else:
                wave_colors = "red|green|blue|yellow|orange|lime|pink|magenta"
        elif colors:
            # Use unified color API (pipe-separated)
            parser = ColorParser(colors)
            wave_colors = parser.as_pipe_colors()
        else:
            wave_colors = "red|green|blue"

        # "pict" mode uses showwavespic (static single-frame), others use showwaves
        if waveform_mode == "pict":
            parts = [
                f"[{audio_index}:a] showwavespic=size={width}x{height}",
                f"colors={wave_colors}",
                "scale=cbrt",
            ]
            if waveform_splits > 1:
                parts.append(f"split_channels={waveform_splits}")
            if waveform_frame and waveform_frame > 0:
                parts.append(f"n={waveform_frame}")
            filter_str = ":".join(parts)
            return f"{filter_str},format=yuv420p[viz]; {bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"

        # Animated modes (line, point, p2p, cline)
        parts = [
            f"[{audio_index}:a] showwaves=size={width}x{height}",
            f"mode={waveform_mode}",
            f"colors={wave_colors}",
            "scale=cbrt",
            f"rate={fps}",
        ]

        if waveform_splits > 1:
            parts.append(f"split_channels={waveform_splits}")

        if waveform_frame and waveform_frame > 0:
            parts.append(f"n={waveform_frame}")

        filter_str = ":".join(parts)

        return (
            f"{filter_str},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
