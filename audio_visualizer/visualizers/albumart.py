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
        **kwargs,
    ) -> str:
        """
        Build the filter_complex for the album art visualizer.

        Effects applied:
        1. Image scaled to output resolution
        2. Subtle color glow overlay (uses colors if provided)
        3. Spectrum bars at the bottom
        4. Composite everything together
        """
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

        return (
            # ── Image Processing ──
            f"[1:v] scale={width}x{height},format=yuv420p[img]; "
            # ── Subtle color glow overlay ──
            f"color=c=ff00ff:s={width}x{height}:r={fps},format=yuva420p,colorchannelmixer=rr={glow_rr}:gg={glow_gg}:bb={glow_bb}:aa={glow_alpha}[glow]; "
            # ── Generate spectrum for overlay ──
            f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
            f"size={width}x{spectrum_height}:scale=log:slide=replace"
            f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
            f":start=0:stop=0,format=yuva420p[spectrum]; "
            # ── Dark bar behind spectrum ──
            f"color=c={bg}:s={width}x{spectrum_height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
            # ── Composite: image + glow + spectrum + darkbar ──
            f"[img][glow] overlay=shortest=1:format=auto[with_glow]; "
            f"[with_glow][spectrum] overlay=0:{spectrum_y}:format=auto[with_spectrum]; "
            f"[with_spectrum][darkbar] overlay=0:{spectrum_y}:format=auto[out]"
        )
