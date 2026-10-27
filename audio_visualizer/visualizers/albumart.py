"""
Album Art Visualizer Plugin

Takes an image (like album art) and creates a visualizer with
audio-reactive effects overlaid on top.

Usage:
    python3 audio_visualizer.py song.mp3 --mode albumart --image album.jpg
"""

import os

from .base import PluginMetadata, VisualizerPlugin
from .colors import ColorParser

# Valid album art effects
ALBUMART_EFFECTS = ("glow", "pulse", "zoom")


class AlbumArtPlugin(VisualizerPlugin):
    """
    Album art visualizer with audio-reactive effects.

    Takes an image and creates a visualizer with:
    - The image as the base background (looped for audio duration)
    - Subtle color glow overlay
    - Spectrum bars at the bottom

    Usage:
        python3 audio_visualizer.py song.mp3 --mode albumart --image album.jpg
    """

    metadata = PluginMetadata(
        name="albumart",
        display_name="Album Art Visualizer",
        description="Uses an image (album art) as background with audio-reactive glow and spectrum overlay",
        author="Audio Visualizer",
        version="1.0.0",
        icon="🎵",
    )

    def build_command(self, args: dict) -> list:
        """
        Override to handle the custom image input.
        """
        image_path = args.get("image")
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(
                f"Image file not found: {image_path}\n"
                f"Use --image /path/to/image.jpg to specify an image"
            )

        width = args["width"]
        height = args["height"]
        fps = args["fps"]

        # Build the complex filter chain
        filter_complex = self.build_filter(
            width, height, fps, image_path, colors=args.get("colors"), bg_color=args.get("bg_color")
        )

        cmd = ["ffmpeg", "-y"]

        # Input 0: audio
        cmd.extend(["-i", args["input"]])
        # Input 1: image (looped for audio duration)
        cmd.extend(["-loop", "1", "-i", image_path])

        cmd.extend(["-filter_complex", filter_complex])

        # Map video output and audio
        cmd.extend(["-map", "[out]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        codec_settings = self._get_codec_settings(fmt, args, accel)

        cmd.extend(codec_settings)
        cmd.extend(
            [
                "-shortest",
                args["output"],
            ]
        )

        return cmd

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        image_path: str = None,
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
        albumart_effect: str = "glow",
        **kwargs,
    ) -> str:
        """
        Build the filter_complex for the album art visualizer.

        Effects applied:
        1. Image scaled to output resolution
        2. Audio-reactive effect (glow/pulse/zoom)
        3. Spectrum bars at the bottom
        4. Composite everything together
        """
        # Validate effect
        if albumart_effect not in ALBUMART_EFFECTS:
            albumart_effect = "glow"

        # Calculate positions
        spectrum_height = int(height * 0.15)  # 15% of height for spectrum
        spectrum_y = height - spectrum_height

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        glow_rr, glow_gg, glow_bb, glow_alpha = parser.as_glow_params()

        # Spectrum color mode from unified API
        color_mode, spectrum_color_mapping = parser.as_spectrum_mode()
        if spectrum_color_mapping:
            spectrum_color_mapping = f":colormapping={spectrum_color_mapping}"

        # Background color: use bg_color arg if provided, otherwise first color or black
        bg = ColorParser(bg_color).as_bg_color() if bg_color else "000000"

        # Build image processing based on effect
        if albumart_effect == "glow":
            # Glow effect: subtle color overlay
            img_proc = (
                f"[1:v] scale={width}x{height},format=yuv420p[img]; "
                f"color=c=ff00ff:s={width}x{height}:r={fps},format=yuva420p,"
                f"colorchannelmixer=rr={glow_rr}:gg={glow_gg}:bb={glow_bb}:aa={glow_alpha}[glow]; "
                f"[img][glow] overlay=shortest=1:format=auto[with_effect]; "
            )
        elif albumart_effect == "pulse":
            # Pulse effect: brightness modulated by audio amplitude
            # Uses aeval to compute mono amplitude, then applies it via colorchannelmixer
            img_proc = (
                f"[1:v] scale={width}x{height},format=yuv420p[img]; "
                f"[0:a] aeval='val(0)+val(1)|0.5',format=flt,asetpts=PTS-STARTPTS[amp]; "
                f"[img]format=rgba,colorchannelmixer=rr=1.0+0.25*am:gg=1.0+0.25*am:bb=1.0+0.25*am:ar=0.0:ag=0.0:ab=0.0:aa=0.0[with_effect]; "
            )
        else:  # zoom
            # Zoom effect: slow Ken Burns zoom using zoompan
            # Zoom from 100% to 115% over 20 seconds, panning slightly
            img_proc = (
                f"[1:v] zoompan=z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={fps * 20}:s={width}x{height},format=yuv420p[with_effect]; "
            )

        return (
            f"{img_proc}"
            f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
            f"size={width}x{spectrum_height}:scale=log:slide=replace"
            f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
            f":start=0:stop=0,format=yuva420p[spectrum]; "
            f"color=c={bg}:s={width}x{spectrum_height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
            f"[with_effect][spectrum] overlay=0:{spectrum_y}:format=auto[with_spectrum]; "
            f"[with_spectrum][darkbar] overlay=0:{spectrum_y}:format=auto[out]"
        )
