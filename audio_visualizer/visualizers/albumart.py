"""
Album Art Visualizer Plugin

Takes an image (like album art) and creates a visualizer with
audio-reactive effects overlaid on top.

Usage:
    python3 audio_visualizer.py song.mp3 --mode albumart --image album.jpg
"""

import os

from .base import PluginMetadata, PluginOption, VisualizerPlugin
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
        category="composite",
        input_types=["audio", "image"],
    )

    options = [
        PluginOption(
            "albumart-effect",
            str,
            "glow",
            "Background effect (glow, pulse, zoom)",
            choices=list(ALBUMART_EFFECTS),
        ),
        PluginOption(
            "albumart-position",
            str,
            "bottom",
            "Spectrum overlay position (bottom, top, left, right, fullscreen)",
            choices=list(ALBUMART_POSITIONS),
        ),
        PluginOption(
            "albumart-glow-intensity",
            float,
            0.08,
            "Glow intensity (0.0-1.0)",
            range=(0.0, 1.0),
        ),
        PluginOption(
            "albumart-fit",
            str,
            "cover",
            "Image fit mode (cover, contain, stretch)",
            choices=list(ALBUMART_FIT_MODES),
        ),
        PluginOption(
            "albumart-blur",
            int,
            0,
            "Gaussian blur radius (0-50)",
            range=(0, 50),
        ),
    ]

    def get_inputs(self, args: dict) -> list[list[str]]:
        """
        Album art uses an image file as the second input instead of a
        background color source.
        """
        image_path = args.get("image")
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(
                f"Image file not found: {image_path}\n"
                f"Use --image /path/to/image.jpg to specify an image"
            )
        return [
            ["-i", args["input"]],
            ["-loop", "1", "-i", image_path],
        ]

    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        options: dict,
        image_path: str | None = None,
        colors: str | None = None,
        bg_color: str | None = None,
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
        # Resolve image path from args if not provided directly
        if image_path is None:
            args = kwargs.get("args", {})
            image_path = args.get("image")

        # Extract options
        albumart_effect = options.get("albumart-effect", "glow")
        albumart_position = options.get("albumart-position", "bottom")
        albumart_glow_intensity = options.get("albumart-glow-intensity", 0.08)
        albumart_fit = options.get("albumart-fit", "cover")
        albumart_blur = options.get("albumart-blur", 0)

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
            # Audio-reactive brightness: a showvolume peak meter drives a
            # screen blend that brightens the image with the volume.
            img_proc = (
                f"{img_scaled}; "
                f"[0:a] showvolume=w=80:h=1:m=0:rate={fps},format=gray,"
                f"scale={width}x{height}:flags=area,format=rgba[amp]; "
                f"[{img_base}]format=rgba[img_rgba]; "
                f"[img_rgba][amp] blend=all_mode=screen:all_opacity=0.3[with_effect]; "
            )
        else:  # zoom
            img_proc = (
                f"{img_scaled}; "
                f"[{img_base}] zoompan=z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={fps * 20}:s={width}x{height},format=yuv420p[with_effect]; "
            )

        # Build spectrum overlay at the correct position. Each branch ends
        # with the main output label [result]; the base class relabels it
        # to [out] (see compose_final_filter).
        if albumart_position == "fullscreen":
            # Spectrum fills entire screen
            return (
                f"{img_proc}"
                f"[0:a] showspectrum=mode=separate:color={color_mode}:saturation=1.5:"
                f"size={width}x{height}:scale=log:slide=replace"
                f":fps={fps}:overlap=0.9:opacity=0.7{spectrum_color_mapping}"
                f",format=yuv420p[result]"
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
                f"[with_spectrum][darkbar] overlay=0:0:format=auto[result]"
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
                f"[with_spectrum][darkbar] overlay={width - spectrum_height}:0:format=auto[result]"
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
                f"[with_effect][spectrum] overlay=0:0:format=auto[with_spectrum2]; "
                f"[with_spectrum2][darkbar] overlay=0:0:format=auto[result]"
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
                f"[with_spectrum][darkbar] overlay=0:{spectrum_y}:format=auto[result]"
            )

    def get_output_label(self, options: dict) -> str:
        return "result"

    def compose_final_filter(self, filter_str: str, main_label: str, args: dict) -> str:
        """Album art composites everything inside build_filter(); just relabel."""
        graph = filter_str.strip()
        if not graph.endswith(";"):
            graph += ";"
        return f"{graph} [{main_label}]format=yuv420p[out]"
