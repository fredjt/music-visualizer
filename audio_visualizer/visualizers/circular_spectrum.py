"""
Circular Spectrum Visualizer Plugin

Displays the audio frequency spectrum wrapped into a true radial/circular shape.
Uses ffmpeg\'s showspectrum filter combined with hstack/vstack/transpose
to wrap the spectrum into a circle.
"""

from .base import PluginMetadata, VisualizerPlugin
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
        circular_spectrum_mode: str = "rainbow",
        circular_spectrum_opacity: float = 1.0,
        **kwargs,
    ) -> str:
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

        # Background: black circle centered in frame
        if bg_color:
            bg = f"color=c={bg_color}:s={width}x{height}:r={fps},format=yuv420p[bg]"
        else:
            bg = f"color=black:s={width}x{height}:r={fps},format=yuv420p[bg]"

        # Build spectrum (separate mode for radial appearance)
        opacity_param = f":opacity={circular_spectrum_opacity:.2f}" if circular_spectrum_opacity < 1.0 else ""
        
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
            f"[ql][qr]hstack=inputs=2[top_half]",
            f"[bl][br]hstack=inputs=2[bottom_half]",
            f"[top_half][bottom_half]vstack=inputs=2[circular]",
        ]

        # Scale circular result to full resolution and overlay on background
        final = [
            f"[circular]scale={width}x{height}[scaled]",
            f"[bg][scaled]overlay=(W-w)/2:(H-h)/2:format=auto[out]",
        ]

        return f"{spectrum}; {'; '.join(quadrants)}; {'; '.join(stacked)}; {'; '.join(final)}"
