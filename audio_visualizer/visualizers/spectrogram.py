"""
Spectrogram Visualizer Plugin

Displays a scrolling spectrogram (waterfall) showing frequency history over time.
Unlike the spectrum mode which shows current frequencies, this shows a historical
view with older data scrolling downward.
"""

from .base import PluginMetadata, VisualizerPlugin

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
        waveform_mode: str = "line",
        waveform_splits: bool = False,
        waveform_frame: int = 0,
        vectorscope_mode: str = "lissajous",
        vectorscope_draw: str = "aaline",
        vectorscope_scale: str = "cbrt",
        vectorscope_zoom: float = 1.0,
        vectorscope_trails: int = 100,
        cqt_gamma: float = 3.0,
        cqt_basefreq: float = 20.0,
        cqt_endfreq: float = 20495.0,
        cqt_attack: float = 0.0,
        cqt_timeclamp: float = 0.17,
        spectrogram_mode: str | None = None,
        **kwargs,
    ) -> str:
        # Validate spectrogram mode
        if spectrogram_mode not in SPECTROGRAM_MODES:
            spectrogram_mode = "intensity"

        # Background: use bg_color fully opaque if provided, otherwise semi-transparent black
        bg_filter = f"[{video_index}:v] format=rgba"
        if bg_color:
            bg_filter += ",colorchannelmixer=aa=1.0"
        else:
            bg_filter += ",colorchannelmixer=aa=0.3"
        bg_filter += "[bg]; "

        # Use a very high overlap to create the waterfall effect
        return (
            f"[{audio_index}:a] showspectrum=mode=separate:color={spectrogram_mode}:saturation=2.0:"
            f"size={width}x{height}:scale=log:slide=rscroll"
            f":fps={fps}:overlap=0.95,format=yuv420p[viz]; "
            f"{bg_filter}[bg][viz] overlay=shortest=1:format=auto [out]"
        )
