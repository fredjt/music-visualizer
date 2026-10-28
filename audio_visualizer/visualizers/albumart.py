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

# Valid album art positions
ALBUMART_POSITIONS = ("bottom", "top", "left", "right", "fullscreen")

# Valid album art fit modes
ALBUMART_FIT_MODES = ("cover", "contain", "stretch")


class AlbumArtPlugin(VisualizerPlugin):
    """
    Album art visualizer with audio-reactive effects.

    Takes an image and creates a visualizer with:
    - The image as the base background (looped for audio duration)
    - Subtle color glow overlay
    - Spectrum bars at a configurable position
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
        albumart_position: str = "bottom",
        albumart_glow_intensity: float = 0.08,
        albumart_fit: str = "cover",
        albumart_blur: int = 0,
        **kwargs,
    ) -> str:
        """
        Build the filter_complex for the album art visualizer.

        Effects applied:
        1. Image scaled to output resolution (with optional blur)
        2. Audio-reactive effect (glow/pulse/zoom)
        3. Spectrum bars at the configured position
        4. Composite everything together
        """
        # Validate effect
        if albumart_effect not in ALBUMART_EFFECTS:
            albumart_effect = "glow"

        # Validate position
        if albumart_position not in ALBUMART_POSITIONS:
            albumart_position = "bottom"

        # Validate fit mode
        if albumart_fit not in ALBUMART_FIT_MODES:
            albumart_fit = "cover"

        # Clamp glow intensity
        albumart_glow_intensity = max(0.0, min(1.0, float(albumart_glow_intensity)))

        # Clamp blur
        albumart_blur = max(0, min(50, int(albumart_blur)))

        # Calculate spectrum area based on position
        spectrum_height = int(height * 0.15)  # 15% of height for spectrum
        spectrum_y = height - spectrum_height  # default: bottom

        if albumart_position == "top":
            spectrum_y = 0
        elif albumart_position == "left":
            spectrum_height = int(height * 0.15)
            spectrum_y = height - spectrum_height
        elif albumart_position == "right":
            spectrum_height = int(height * 0.15)
            spectrum_y = height - spectrum_height
        elif albumart_position == "fullscreen":
            spectrum_height = height
            spectrum_y = 0

        # Unified color handling via ColorParser
        parser = ColorParser(colors)
        glow_rr, glow_gg, glow_bb, glow_alpha = parser.as_glow_params(
            alpha_multiplier=albumart_glow_intensity,
            mix_multiplier=albumart_glow_intensity * 2,
        )

        # Spectrum color mode from unified API
        color_mode, spectrum_color_mapping = parser.as_spectrum_mode()
        if spectrum_color_mapping:
            spectrum_color_mapping = f":colormapping={spectrum_color_mapping}"

        # Background color: use bg_color arg if provided, otherwise first color or black
        bg = ColorParser(bg_color).as_bg_color() if bg_color else "000000"

        # Build image processing based on fit mode
        if albumart_fit == "cover":
            # Crop to fill (default)
            img_scaled = f"[1:v] scale={width}x{height},format=yuv420p[img]"
        elif albumart_fit == "contain":
            # Letterbox to fit within bounds
            img_scaled = f"[1:v] scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg},format=yuv420p[img]"
        else:  # stretch
            img_scaled = f"[1:v] scale={width}x{height},format=yuv420p[img]"

        # Apply blur if requested
        if albumart_blur > 0:
            img_scaled += f",boxblur={albumart_blur}:{albumart_blur}[img_blurred]"
            img_base = "img_blurred"
        else:
            img_base = "img"

        # Apply effect
        if albumart_effect == "glow":
            img_proc = (
                f"{img_scaled}; "
                f"color=c=ff00ff:s={width}x{height}:r={fps},format=yuva420p,"
                f"colorchannelmixer=rr={glow_rr}:gg={glow_gg}:bb={glow_bb}:aa={glow_alpha}[glow]; "
                f"[{img_base}][glow] overlay=shortest=1:format=auto[with_effect]; "
            )
        elif albumart_effect == "pulse":
            img_proc = (
                f"{img_scaled}; "
                f"[0:a] aeval=\'val(0)+val(1)|0.5\',format=flt,asetpts=PTS-STARTPTS[amp]; "
                f"[{img_base}]format=rgba,colorchannelmixer=rr=1.0+0.25*am:gg=1.0+0.25*am:bb=1.0+0.25*am:ar=0.0:ag=0.0:ab=0.0:aa=0.0[with_effect]; "
            )
        else:  # zoom
            img_proc = (
                f"{img_scaled}; "
                f"[{img_base}] zoompan=z=\'min(zoom+0.0015,1.15)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':"
                f"d={fps * 20}:s={width}x{height},format=yuv420p[with_effect]; "
            )

        # Build spectrum overlay at the correct position
        if albumart_position == "fullscreen":
            # Spectrum fills entire screen
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={width}x{height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuv420p[out]"
            )
        elif albumart_position == "left":
            # Spectrum on the left side
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={spectrum_height}x{height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuva420p[spectrum]; "
                f"color=c={bg}:s={spectrum_height}x{height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
                f"[with_effect][spectrum] overlay=0:0:format=auto[with_spectrum]; "
                f"[with_spectrum][darkbar] overlay=0:0:format=auto[out]"
            )
        elif albumart_position == "right":
            # Spectrum on the right side
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={spectrum_height}x{height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuva420p[spectrum]; "
                f"color=c={bg}:s={spectrum_height}x{height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
                f"[with_effect][spectrum] overlay={width - spectrum_height}:0:format=auto[with_spectrum]; "
                f"[with_spectrum][darkbar] overlay={width - spectrum_height}:0:format=auto[out]"
            )
        elif albumart_position == "top":
            # Spectrum at the top
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={width}x{spectrum_height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuva420p[spectrum]; "
                f"color=c={bg}:s={width}x{spectrum_height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
                f"[with_spectrum][spectrum] overlay=0:0:format=auto[with_spectrum2]; "
                f"[with_spectrum2][darkbar] overlay=0:0:format=auto[out]"
            )
        else:  # bottom (default)
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={width}x{spectrum_height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuva420p[spectrum]; "
                f"color=c={bg}:s={width}x{spectrum_height}:r={fps},format=yuva420p,colorchannelmixer=aa=0.4[darkbar]; "
                f"[with_effect][spectrum] overlay=0:{spectrum_y}:format=auto[with_spectrum]; "
                f"[with_spectrum][darkbar] overlay=0:{spectrum_y}:format=auto[out]"
            )
