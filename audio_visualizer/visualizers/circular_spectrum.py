"""
Circular Spectrum Visualizer Plugin

Displays the audio frequency spectrum wrapped into a true radial/circular shape.
Uses ffmpeg\'s showspectrum filter combined with hstack/vstack/transpose
to wrap the spectrum into a circle.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .colors import ColorParser


class CircularSpectrumPlugin(VisualizerPlugin):
    """
    True radial/circular spectrum visualization.

    Wraps the frequency spectrum into a circle using ffmpeg filters.
    Creates a radar-like display where frequencies radiate from center.
    """

    metadata = PluginMetadata(
        name="circular-spectrum",
        display_name="Circular Spectrum",
        description="True radial/circular spectrum using hstack/vstack/transpose",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🔵",
        category="spectrum",
    )

    options = [
        PluginOption(
            "circular-spectrum-mode",
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
            "circular-spectrum-opacity",
            float,
            1.0,
            "Spectrum opacity (0.0-1.0)",
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
        circular_spectrum_mode = options.get("circular-spectrum-mode", "rainbow")
        circular_spectrum_opacity = options.get("circular-spectrum-opacity", 1.0)

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        color_mapping = ""
        if colors and circular_spectrum_mode == "colormapping":
            _, color_mapping = parser.as_spectrum_mode()
            if color_mapping:
                color_mapping = f":colormapping={color_mapping}"

        # Clamp opacity
        circular_spectrum_opacity = max(0.0, min(1.0, float(circular_spectrum_opacity)))

        # For circular spectrum, we create a smaller spectrum and wrap it
        # Half resolution for the spectrum so it fits in a circle
        spec_w = width // 2
        spec_h = height // 2

        # Build spectrum (separate mode for radial appearance)
        opacity_param = (
            f":opacity={circular_spectrum_opacity:.2f}" if circular_spectrum_opacity < 1.0 else ""
        )

        spectrum = (
            f"[{audio_index}:a] showspectrum=mode=separate:color={circular_spectrum_mode}"
            f":saturation=2.0:size={spec_w}x{spec_h}:scale=log:slide=replace"
            f":fps={fps}:overlap=0.9{opacity_param}{color_mapping}"
            f",format=yuv420p[spectrum]"
        )

        # Create 4 quadrants by splitting the spectrum and flipping the
        # copies. A filtergraph label can only be consumed once, so the
        # single [spectrum] output must be fanned out with split=4.
        # Top-right: original spectrum
        # Top-left: horizontally flipped
        # Bottom-right: vertically flipped
        # Bottom-left: both flipped
        quadrants = [
            f"[q1]scale={spec_w}x{spec_h}[qr]",
            f"[q2]hflip,scale={spec_w}x{spec_h}[ql]",
            f"[q3]vflip,scale={spec_w}x{spec_h}[br]",
            f"[q4]hflip,vflip,scale={spec_w}x{spec_h}[bl]",
        ]

        # Stack left pair and right pair, then stack those
        stacked = [
            "[ql][qr]hstack=inputs=2[top_half]",
            "[bl][br]hstack=inputs=2[bottom_half]",
            "[top_half][bottom_half]vstack=inputs=2[circular]",
        ]

        # Scale circular result to full resolution. The base class
        # composes the final [out] (see compose_final_filter for the
        # centered overlay on a solid background).
        final = f"[circular]scale={width}x{height}[scaled]"

        return (
            f"{spectrum}; "
            f"[spectrum]split=4[q1][q2][q3][q4]; "
            f"{'; '.join(quadrants)}; "
            f"{'; '.join(stacked)}; "
            f"{final}"
        )

    def get_inputs(self, args: dict) -> list[list[str]]:
        """Circular spectrum builds its own background inside the filter graph."""
        return [["-i", args["input"]]]

    def get_output_label(self, options: dict) -> str:
        return "scaled"

    def compose_final_filter(self, filter_str: str, main_label: str, args: dict) -> str:
        """Center the circular spectrum on a solid background."""
        width = args["width"]
        height = args["height"]
        graph = filter_str.strip()
        if not graph.endswith(";"):
            graph += ";"
        return (
            f"{graph} nullsrc=size={width}x{height},format=yuv420p[bg]; "
            f"[bg][{main_label}]overlay=(W-w)/2:(H-h)/2:format=auto[out]"
        )
