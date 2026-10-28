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
                "channel", "intensity", "rainbow", "moreland", "nebulae", "fire", "fiery",
                "fruit", "cool", "magma", "green", "viridis", "plasma", "cividis", "terrain",
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

        # Create 4 quadrants by transposing and flipping
        # Top-right: original spectrum
        # Top-left: horizontally flipped
        # Bottom-right: vertically flipped
        # Bottom-left: both flipped
        quadrants = [
            f"[spectrum]scale={spec_w}x{spec_h}[qr]",
            f"[spectrum]hflip,scale={spec_w}x{spec_h}[ql]",
            f"[spectrum]vflip,scale={spec_w}x{spec_h}[br]",
            f"[spectrum]hflip,vflip,scale={spec_w}x{spec_h}[bl]",
        ]

        # Stack left pair and right pair, then stack those
        stacked = [
            "[ql][qr]hstack=inputs=2[top_half]",
            "[bl][br]hstack=inputs=2[bottom_half]",
            "[top_half][bottom_half]vstack=inputs=2[circular]",
        ]

        # Create background
        bg_filter = f"nullsrc=size={width}x{height},format=yuv420p[bg]; "

        # Scale circular result to full resolution and overlay on background
        final = [
            f"[circular]scale={width}x{height}[scaled]",
            "[bg][scaled]overlay=(W-w)/2:(H-h)/2:format=auto[out]",
        ]

        return f"{spectrum}; {'; '.join(quadrants)}; {'; '.join(stacked)}; {bg_filter}{'; '.join(final)}"
