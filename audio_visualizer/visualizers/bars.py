"""
Bars Visualizer Plugin

Displays a classic bar spectrum with customizable width, spacing,
orientation, and rounded bar tops. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


class BarsPlugin(VisualizerPlugin):
    """
    Classic bar spectrum visualization with custom parameters.

    Shows the frequency spectrum as bars with configurable:
    - bar width/thickness in pixels
    - spacing between bars
    - orientation (horizontal/vertical)
    - rounded bar tops
    """

    metadata = PluginMetadata(
        name="bars",
        display_name="Classic Bars",
        description="Classic bar spectrum with customizable width, spacing, orientation, and rounded tops",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📊",
        category="spectrum",
    )

    options = [
        PluginOption(
            "bar-width",
            int,
            0,
            "Bar width in pixels (0 = auto)",
            range=(0, None),
        ),
        PluginOption(
            "bar-spacing",
            float,
            0.5,
            "Bar spacing (0.0-1.0)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "bar-orientation",
            str,
            "horizontal",
            "Bar orientation (horizontal, vertical)",
            choices=["horizontal", "vertical"],
        ),
        PluginOption(
            "bar-radius",
            int,
            0,
            "Bar top radius in pixels (0 = square)",
            range=(0, None),
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
        bar_width = options.get("bar-width", 0)
        bar_spacing = options.get("bar-spacing", 0.5)
        bar_orientation = options.get("bar-orientation", "horizontal")
        bar_radius = options.get("bar-radius", 0)

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Clamp bar width (0 = use ffmpeg default)
        bar_width = max(0, min(width // 2, int(bar_width)))

        # Clamp bar spacing (0.0 = no gap, 1.0 = maximum gap)
        bar_spacing = max(0.0, min(1.0, float(bar_spacing)))

        # Validate orientation
        if bar_orientation not in ("horizontal", "vertical"):
            bar_orientation = "horizontal"

        # Clamp bar radius
        bar_radius = max(0, min(min(width, height) // 4, int(bar_radius)))

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        # Orientation: horizontal (default) vs vertical
        if bar_orientation == "vertical":
            return (
                f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
                f"size={height}x{width}:scale=log:slide=scroll"
                f":fps={fps}:overlap={bar_spacing}{color_mapping},format=yuv420p[viz]; "
                f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
            )

        # Horizontal bars (default)
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap={bar_spacing}{color_mapping},format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
