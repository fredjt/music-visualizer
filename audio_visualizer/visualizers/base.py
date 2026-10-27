"""
Base Visualizer Plugin

All visualizer plugins must inherit from this class and implement
defined methods. The core system uses these interfaces to build
ffmpeg filter graphs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PluginMetadata:
    """Metadata describing a visualizer plugin."""

    name: str  # Unique identifier (e.g., 'spectrum')
    display_name: str  # Human-readable name (e.g., 'Color Spectrum')
    description: str  # What the visualization does
    author: str | None = None  # Plugin author
    version: str = "1.0.0"  # Plugin version
    icon: str | None = None  # Emoji/icon for display


class VisualizerPlugin(ABC):
    """
    Base class for audio visualizer plugins.

    Every visualizer plugin must:
    1. Inherit from this class
    2. Define a `metadata` class attribute (or property)
    3. Implement `build_filter()` to return the ffmpeg filter_complex string

    The core system handles:
    - Plugin discovery and registration
    - Audio input/output handling
    - ffmpeg execution
    - Error reporting

    Example plugin:
        class MyPlugin(VisualizerPlugin):
            metadata = PluginMetadata(
                name="my_viz",
                display_name="My Visualizer",
                description="Does cool stuff",
            )

            def build_filter(self, width: int, height: int, fps: int,
                             audio_index: int, video_index: int) -> str:
                return f"[{audio_index}:a] myfilter=size={width}x{height}[viz]; ..."
    """

    # Override this with plugin metadata
    metadata: PluginMetadata = None  # type: ignore

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Return the plugin's metadata."""
        if cls.metadata is None:
            raise NotImplementedError(f"{cls.__name__} must define a 'metadata' class attribute")
        return cls.metadata

    @abstractmethod
    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        audio_index: int = 0,
        video_index: int = 1,
        colors: str | None = None,
        **kwargs,
    ) -> str:
        """
        Build the ffmpeg filter_complex string for this visualizer.

        Args:
            width: Output video width in pixels
            height: Output video height in pixels
            fps: Frame rate (frames per second)
            audio_index: Index of the audio input stream in ffmpeg command
            video_index: Index of the black background video input
            colors: Color string for the visualizer
            **kwargs: Additional plugin-specific options (e.g., waveform_mode)

        Returns:
            A complete filter_complex string that produces an '[out]' labeled output.
            The filter should consume audio from [audio_index]:a and optionally
            use [video_index]:v as a background.

        Example return value:
            "[0:a] showspectrum=size=1280x720:scale=log[viz]; "
            "[1:v][viz] overlay=shortest=1[out]"
        """
        pass

    def build_command(self, args: dict) -> list:
        """
        Build the complete ffmpeg command for this plugin.

        Override this to customize the ffmpeg command (e.g., add custom inputs,
        change encoding settings). The default implementation handles the common case.

        Args:
            args: Dictionary with keys:
                - input: Input audio file path
                - output: Output video file path
                - width: Output width
                - height: Output height
                - fps: Frame rate
                - preset: x264 preset
                - crf: Constant Rate Factor
                - format: Output format (mp4, mkv, webm, avi, mov, flv)
                - accel: Hardware acceleration (sw, nvenc, qsv, vaapi)

        Returns:
            List of ffmpeg command arguments
        """
        # Pass all args as kwargs to build_filter
        filter_kwargs = {
            "width": args["width"],
            "height": args["height"],
            "fps": args["fps"],
            "colors": args.get("colors"),
            "bg_color": args.get("bg_color"),
        }
        # Forward waveform-specific options
        for key in ("waveform_mode", "waveform_splits", "waveform_frame"):
            val = args.get(key)
            if val is not None:
                filter_kwargs[key] = val
        # Default waveform_splits to 1 if not provided
        if "waveform_splits" not in filter_kwargs:
            filter_kwargs["waveform_splits"] = 1
        # Forward vectorscope-specific options
        for key in (
            "vectorscope_mode",
            "vectorscope_draw",
            "vectorscope_scale",
            "vectorscope_zoom",
            "vectorscope_trails",
        ):
            val = args.get(key)
            if val is not None:
                filter_kwargs[key] = val
        # Forward CQT-specific options
        for key in ("cqt_gamma", "cqt_basefreq", "cqt_endfreq", "cqt_attack", "cqt_timeclamp"):
            val = args.get(key)
            if val is not None:
                filter_kwargs[key] = val
        # Forward radial-specific options
        for key in ("mirror_axis", "mirror_gap"):
            val = args.get(key)
            if val is not None:
                filter_kwargs[key] = val
        # Forward spectrum-specific options
        for key in ("spectrum_mode",):
            val = args.get(key)
            if val is not None:
                filter_kwargs[key] = val
        filter_complex = self.build_filter(**filter_kwargs)

        # Determine codec and settings based on format
        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        codec_settings = self._get_codec_settings(fmt, args, accel)

        cmd = ["ffmpeg", "-y", "-i", args["input"]]

        # Add background video source (black by default, or custom bg_color)
        bg_color = args.get("bg_color") or "black"
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c={bg_color}:s={args['width']}x{args['height']}:r={args['fps']}",
            ]
        )

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[out]", "-map", "0:a?"])
        cmd.extend(codec_settings)
        cmd.extend(
            [
                "-shortest",
                args["output"],
            ]
        )

        return cmd

    def _get_codec_settings(self, fmt: str, args: dict, accel: str = "sw") -> list:
        """
        Get codec settings based on output format and hardware acceleration.

        Args:
            fmt: Output format (mp4, mkv, webm, avi, mov, flv)
            args: Arguments dictionary
            accel: Hardware acceleration method (sw, nvenc, qsv, vaapi)

        Returns:
            List of codec-related ffmpeg arguments
        """
        preset = args.get("preset", "medium")
        crf = args.get("crf", 23)

        # Hardware acceleration settings
        # Note: Hardware encoders use different quality scales than software
        hw_settings = {
            "nvenc": {
                "vcodec": "h264_nvenc",
                "pix_fmt": "yuv420p",
                # NVENC uses CQ mode, quality scale is different from libx264
                # CRF 23 roughly maps to CQ 20-23
                "extra": ["-movflags", "+faststart", "-rc", "vbr", "-cq", str(min(crf + 3, 51))],
            },
            "qsv": {
                "vcodec": "h264_qsv",
                "pix_fmt": "nv12",
                # QSV uses global_quality scale (1-31, lower=better)
                "extra": ["-movflags", "+faststart", "-global_quality", str(max(1, 31 - crf))],
            },
            "vaapi": {
                "vcodec": "h264_vaapi",
                "pix_fmt": "nv12",
                # VA-API uses qscale (1-31, lower=better)
                "extra": ["-movflags", "+faststart", "-q", str(max(1, 31 - crf))],
            },
        }

        # Software encoding settings
        sw_format_codecs = {
            "mp4": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "extra": ["-movflags", "+faststart"],
            },
            "mkv": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "extra": [],
            },
            "webm": {
                "vcodec": "libvpx-vp9",
                "pix_fmt": "yuv420p",
                "extra": [],
            },
            "avi": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "extra": [],
            },
            "mov": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "extra": ["-movflags", "+faststart"],
            },
            "flv": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "extra": [],
            },
        }

        if accel in hw_settings:
            settings = hw_settings[accel]
            return [
                "-c:v",
                settings["vcodec"],
                "-preset",
                preset,
                "-pix_fmt",
                settings["pix_fmt"],
            ] + settings["extra"]
        else:
            # Software encoding
            settings = sw_format_codecs.get(fmt, sw_format_codecs["mp4"])
            return [
                "-c:v",
                settings["vcodec"],
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                settings["pix_fmt"],
            ] + settings["extra"]
