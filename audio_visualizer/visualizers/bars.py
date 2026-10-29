"""
Bars Visualizer Plugin

Displays a classic bar spectrum with customizable spacing and
orientation. Uses ffmpeg's showspectrum filter.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


class BarsPlugin(VisualizerPlugin):
    """
    Classic bar spectrum visualization with custom parameters.

    Shows the frequency spectrum as bars with configurable:
    - spacing between bars
    - orientation (horizontal/vertical)
    """

    metadata = PluginMetadata(
        name="bars",
        display_name="Classic Bars",
        description="Classic bar spectrum with customizable spacing and orientation",
        author="Audio Visualizer",
        version="1.0.0",
        icon="📊",
        category="spectrum",
    )

    options = [
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
        bar_spacing = options.get("bar-spacing", 0.5)
        bar_orientation = options.get("bar-orientation", "horizontal")

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Clamp bar spacing (0.0 = no gap, 1.0 = maximum gap)
        bar_spacing = max(0.0, min(1.0, float(bar_spacing)))

        # Validate orientation
        if bar_orientation not in ("horizontal", "vertical"):
            bar_orientation = "horizontal"

        # The base class composes the final [out] by overlaying [viz]
        # on the background input.

        # Orientation: horizontal (default) vs vertical. Vertical bars are
        # generated at the transposed size (height x width) and rotated
        # back so the output keeps the requested width x height.
        if bar_orientation == "vertical":
            return (
                f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
                f"size={height}x{width}:scale=log:slide=scroll"
                f":fps={fps}:overlap={bar_spacing}{color_mapping},"
                f"format=yuv420p,transpose=2[viz]"
            )

        # Horizontal bars (default)
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap={bar_spacing}{color_mapping},format=yuv420p[viz]"
        )
