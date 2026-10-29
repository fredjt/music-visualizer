"""
Color Spectrum Visualizer Plugin

Displays a colorful frequency spectrum with vertical bars that scroll
from right to left. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


class SpectrumPlugin(VisualizerPlugin):
    """
    Colorful frequency spectrum visualization.

    Shows audio frequencies as colored vertical bars that scroll
    across the screen. Low frequencies are at the bottom (red/orange),
    high frequencies fade to blue/purple at the top.
    """

    metadata = PluginMetadata(
        name="spectrum",
        display_name="Color Spectrum",
        description="Colorful frequency spectrum with vertical bars that scroll across the screen",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🌈",
        category="spectrum",
    )

    options = [
        PluginOption(
            "spectrum-mode",
            str,
            "rainbow",
            "Colormap mode (rainbow, fire, magma, viridis, etc.)",
            choices=[
                "channel",
                "intensity",
                "rainbow",
                "moreland",
                "nebulae",
                "fire",
                "fiery",
                "fruit",
                "cool",
                "magma",
                "green",
                "viridis",
                "plasma",
                "cividis",
                "terrain",
                "colormapping",
            ],
        ),
        PluginOption(
            "spectrum-style",
            str,
            "scroll",
            "Slide mode (replace, scroll, fill)",
            choices=["replace", "scroll", "fill"],
        ),
        PluginOption(
            "spectrum-opacity",
            float,
            1.0,
            "Spectrum opacity (0.0-1.0)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "spectrum-start",
            float,
            0,
            "Start frequency for display range (Hz)",
        ),
        PluginOption(
            "spectrum-stop",
            float,
            0,
            "Stop frequency for display range (Hz)",
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
        spectrum_mode = options.get("spectrum-mode", "rainbow")
        spectrum_style = options.get("spectrum-style", "scroll")
        spectrum_opacity = options.get("spectrum-opacity", 1.0)
        spectrum_start = options.get("spectrum-start", 0)
        spectrum_stop = options.get("spectrum-stop", 0)

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mapping = ""
        if colors and spectrum_mode == "colormapping":
            _, color_mapping = parser.as_spectrum_mode()
            if color_mapping:
                color_mapping = f":colormapping={color_mapping}"
        elif colors and spectrum_mode != "colormapping":
            # If colors provided with non-colormapping mode, ignore colors
            pass

        # Map spectrum_style to slide mode
        style_map = {
            "replace": "replace",
            "scroll": "scroll",
            "fill": "fill",
        }
        slide_mode = style_map.get(spectrum_style, "scroll")

        # Clamp opacity
        spectrum_opacity = max(0.0, min(1.0, float(spectrum_opacity)))
        opacity_param = f":opacity={spectrum_opacity:.2f}" if spectrum_opacity < 1.0 else ""

        # Build start/stop params for frequency range restriction
        freq_params = ""
        if spectrum_start > 0:
            freq_params += f":start={spectrum_start}"
        if spectrum_stop > 0:
            freq_params += f":stop={spectrum_stop}"

        # The base class composes the final [out] by overlaying [viz]
        # on the background input.
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={spectrum_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide={slide_mode}"
            f":fps={fps}:overlap=0.8{opacity_param}{color_mapping}{freq_params},format=yuv420p[viz]"
        )
