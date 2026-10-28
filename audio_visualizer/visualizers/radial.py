"""
Mirrored Spectrum Visualizer Plugin

Displays a symmetrical spectrum with top/bottom reflection.
The original spectrum appears on top, and a vertically-flipped
copy appears below, creating a mirror effect.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


class RadialPlugin(VisualizerPlugin):
    """
    Symmetrical mirrored spectrum visualization.

    Shows the frequency spectrum reflected both upward and downward
    from a center line, creating a symmetrical mirror effect.
    The result is scaled back to the target resolution.
    """

    metadata = PluginMetadata(
        name="radial",
        display_name="Mirrored Spectrum",
        description="Symmetrical spectrum with configurable mirror axis (x, y, or xy)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🪞",
        category="spectrum",
    )

    options = [
        PluginOption(
            "mirror-axis",
            str,
            "y",
            "Mirror axis (x, y, xy)",
            choices=["x", "y", "xy"],
        ),
        PluginOption(
            "mirror-gap",
            int,
            0,
            "Gap pixels between original and mirrored halves",
            range=(0, None),
        ),
        PluginOption(
            "mirror-opacity",
            float,
            1.0,
            "Opacity of mirrored half (0.0-1.0)",
            range=(0.0, 1.0),
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
        mirror_axis = options.get("mirror-axis", "y")
        mirror_gap = options.get("mirror-gap", 0)
        mirror_opacity = options.get("mirror-opacity", 1.0)

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mode, color_mapping = parser.as_spectrum_mode()
        if color_mapping:
            color_mapping = f":colormapping={color_mapping}"

        # Clamp mirror opacity
        mirror_opacity = max(0.0, min(1.0, float(mirror_opacity)))
        opacity_param = f":opacity={mirror_opacity:.2f}" if mirror_opacity < 1.0 else ""

        # Validate mirror axis
        if mirror_axis not in ("x", "y", "xy"):
            mirror_axis = "y"

        # Build background source
        if bg_color:
            bg_src = f"color=c={bg_color}:s={width}x{height * 2},format=yuv420p[bg]"
        else:
            bg_src = (
                f"nullsrc=size={width}x{height * 2},format=yuv420p,colorchannelmixer=aa=0.3[bg]"
            )

        # Select flip operation based on mirror axis
        if mirror_axis == "x":
            flip_op = "hflip"
        elif mirror_axis == "xy":
            flip_op = "hflip,vflip"
        else:  # default "y"
            flip_op = "vflip"

        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={color_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=scroll"
            f":fps={fps}:overlap=0.7{opacity_param}{color_mapping},format=yuv420p[spectrum]; "
            f"[spectrum] split=2[top_copy][flip_src]; "
            f"[flip_src] {flip_op},scale={width}x{height}[flipped]; "
            # Stack original on top, flipped on bottom, scale to target
            f"{bg_src}; "
            f"[bg][top_copy] overlay=shortest=1:format=auto[top]; "
            f"[top][flipped] overlay=shortest=1:y={height}+{mirror_gap}:format=auto[mirrored]; "
            f"[mirrored] format=yuv420p,scale={width}x{height}[out]"
        )
