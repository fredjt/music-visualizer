"""
Spectrogram Visualizer Plugin

Displays a scrolling spectrogram (waterfall) showing frequency history over time.
Unlike the spectrum mode which shows current frequencies, this shows a historical
view with older data scrolling downward.
"""

from .base import PluginMetadata, PluginOption, VisualizerPlugin
from .utils import build_background, compose_output

# Valid spectrogram colormapping modes
SPECTROGRAM_MODES = ("intensity", "rain", "fire", "heat", "ice", "swirl")


class SpectrogramPlugin(VisualizerPlugin):
    """
    Scrolling spectrogram / waterfall visualization.

    Shows frequency content over time with a scrolling effect.
    Low frequencies are at the bottom (red/orange), high frequencies
    fade to blue/purple at the top. Older data scrolls downward.
    """

    metadata = PluginMetadata(
        name="spectrogram",
        display_name="Spectrogram Waterfall",
        description="Scrolling spectrogram showing frequency history over time (waterfall view)",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🌊",
        category="spectrum",
    )

    options = [
        PluginOption(
            "spectrogram-mode",
            str,
            "intensity",
            "Colormap mode (intensity, rain, fire, heat, ice, swirl)",
            choices=list(SPECTROGRAM_MODES),
        ),
        PluginOption(
            "spectrogram-speed",
            float,
            0.95,
            "Scroll speed (0.0-1.0, higher = slower)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "spectrogram-opacity",
            float,
            1.0,
            "Waterfall opacity (0.0-1.0)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "spectrogram-transpose",
            bool,
            False,
            "Rotate spectrogram 90 degrees",
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
        spectrogram_mode = options.get("spectrogram-mode", "intensity")
        spectrogram_speed = options.get("spectrogram-speed", 0.95)
        spectrogram_opacity = options.get("spectrogram-opacity", 1.0)
        spectrogram_transpose = options.get("spectrogram-transpose", False)

        # Validate spectrogram mode
        if spectrogram_mode not in SPECTROGRAM_MODES:
            spectrogram_mode = "intensity"

        # Clamp speed (overlap value controls scroll speed: higher = slower)
        spectrogram_speed = max(0.0, min(1.0, float(spectrogram_speed)))

        # Clamp opacity
        spectrogram_opacity = max(0.0, min(1.0, float(spectrogram_opacity)))
        opacity_param = f":opacity={spectrogram_opacity:.2f}" if spectrogram_opacity < 1.0 else ""

        # Background
        bg_filter = build_background(video_index, bg_color)

        # Build the spectrogram filter
        spec_filter = (
            f"[{audio_index}:a] showspectrum=mode=separate:color={spectrogram_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=rscroll"
            f":fps={fps}:overlap={spectrogram_speed:.2f}{opacity_param},format=yuv420p[viz]"
        )

        # Apply transpose if requested (swap time/frequency axes)
        if spectrogram_transpose:
            return (
                f"{spec_filter}; [viz]transpose=1[transposed]; "
                f"{bg_filter}[bg][transposed]overlay=shortest=1:format=auto[out]"
            )
        else:
            return compose_output(spec_filter + "; ", bg_filter)
