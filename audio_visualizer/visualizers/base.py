"""
Base Visualizer Plugin

All visualizer plugins must inherit from this class and implement
defined methods. The core system uses these interfaces to build
ffmpeg filter graphs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginOption:
    """Schema definition for a plugin option.

    Each plugin declares its options via a class-level `options` list.
    The CLI and base class use these schemas to validate, forward, and
    generate help text — no hardcoded parameter lists needed.
    """

    name: str  # CLI flag name (without --), e.g., "spectrum-mode"
    type: type  # Python type: str, int, float, bool
    default: Any  # Default value when not provided
    help: str = ""  # Help text for CLI
    choices: list | None = None  # Allowed values (optional)
    range: tuple | None = None  # (min, max) numeric range (optional)
    group: str | None = None  # Option group for CLI organization (optional)

    def validate(self, value: Any) -> Any:
        """Validate and coerce a value to the option's type.

        Returns the validated/coerced value.
        Raises ValueError if validation fails.
        """
        if value is None:
            return self.default

        # Type coercion
        try:
            value = self.type(value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Option '{self.name}': expected {self.type.__name__}, got {type(value).__name__}"
            )

        # Choices validation
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Option '{self.name}': value '{value}' not in {self.choices}")

        # Range validation (for numeric types)
        if self.range is not None and isinstance(value, (int, float)):
            min_val, max_val = self.range
            if value < min_val or value > max_val:
                raise ValueError(
                    f"Option '{self.name}': value {value} not in range [{min_val}, {max_val}]"
                )

        return value

    def to_cli_arg(self) -> str:
        """Convert option name to CLI argument format (--option-name)."""
        return f"--{self.name.replace('_', '-')}"


@dataclass
class PluginMetadata:
    """Metadata describing a visualizer plugin."""

    name: str  # Unique identifier (e.g., 'spectrum')
    display_name: str  # Human-readable name (e.g., 'Color Spectrum')
    description: str  # What the visualization does
    author: str | None = None  # Plugin author
    version: str = "1.0.0"  # Plugin version
    icon: str | None = None  # Emoji/icon for display
    category: str = "other"  # Plugin category for grouping (spectrum, waveform, meter, composite)
    requires_ffmpeg_version: str | None = None  # Minimum ffmpeg version (e.g., "7.0")
    input_types: list[str] = field(default_factory=lambda: ["audio"])  # Required input types


class VisualizerPlugin(ABC):
    """
    Base class for audio visualizer plugins.

    Every visualizer plugin must:
    1. Inherit from this class
    2. Define a `metadata` class attribute (or property)
    3. Define an `options` list of PluginOption instances
    4. Implement `build_filter()` to return the ffmpeg filter_complex string

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
            options = [
                PluginOption("mode", str, "default", "Display mode", choices=["default", "advanced"]),
            ]

            def build_filter(self, width: int, height: int, fps: int,
                             options: dict, audio_index: int = 0,
                             video_index: int = 1) -> str:
                mode = options.get("mode", "default")
                return f"[{audio_index}:a] myfilter=size={width}x{height}[viz]; ..."
    """

    # Override these with plugin metadata and options
    metadata: PluginMetadata = None  # type: ignore
    options: list[PluginOption] = []  # Plugin-specific option schemas
    category: str = "other"  # Plugin category for grouping
    required_inputs: list[str] = field(default_factory=lambda: ["audio"])  # Required input types

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Return the plugin's metadata."""
        if cls.metadata is None:
            raise NotImplementedError(f"{cls.__name__} must define a 'metadata' class attribute")
        return cls.metadata

    @classmethod
    def get_options(cls) -> dict[str, PluginOption]:
        """Return plugin options as {name: PluginOption} dict."""
        return {opt.name: opt for opt in cls.options}

    @classmethod
    def validate_options(cls, options: dict) -> dict:
        """Validate and coerce options against the plugin's schema.

        Returns a dict with validated/coerced values.
        Options not in the schema are passed through unchanged.
        Missing options get their default values.
        """
        validated = {}
        schema = cls.get_options()

        # Apply defaults for missing options
        for opt_name, opt in schema.items():
            validated[opt_name] = opt.default

        # Validate and coerce provided options
        for opt_name, value in options.items():
            if opt_name in schema:
                validated[opt_name] = schema[opt_name].validate(value)
            else:
                # Unknown option — pass through (may be used by base class)
                validated[opt_name] = value

        return validated

    @abstractmethod
    def build_filter(
        self,
        width: int,
        height: int,
        fps: int,
        options: dict,
        audio_index: int = 0,
        video_index: int = 1,
    ) -> str:
        """
        Build the ffmpeg filter_complex string for this visualizer.

        Args:
            width: Output video width in pixels
            height: Output video height in pixels
            fps: Frame rate (frames per second)
            options: Validated plugin options dict (from plugin's schema)
            audio_index: Index of the audio input stream in ffmpeg command
            video_index: Index of the black background video input

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
                - colors: Color string for the visualizer
                - bg_color: Background color
                - border: Enable border
                - border_color: Border color
                - border_width: Border width
                - <plugin-specific options>: Values from CLI flags

        Returns:
            List of ffmpeg command arguments
        """
        # Extract global args
        width = args["width"]
        height = args["height"]
        fps = args["fps"]
        colors = args.get("colors")
        bg_color = args.get("bg_color")

        # Extract plugin-specific options from args using the plugin's schema
        schema = self.get_options()
        plugin_options = {}
        for opt in schema.values():
            val = args.get(opt.name)
            if val is not None:
                plugin_options[opt.name] = val

        # Validate options against schema (applies defaults for missing options)
        plugin_options = self.validate_options(plugin_options)

        # Build filter graph
        filter_complex = self.build_filter(
            width=width,
            height=height,
            fps=fps,
            options=plugin_options,
            colors=colors,
            bg_color=bg_color,
        )

        # Determine codec and settings based on format
        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        codec_settings = self._get_codec_settings(fmt, args, accel)

        cmd = ["ffmpeg", "-y", "-i", args["input"]]

        # Add background video source (black by default, or custom bg_color)
        bg_color_input = bg_color or "black"
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c={bg_color_input}:s={width}x{height}:r={fps}",
            ]
        )

        # Add border if enabled
        border_args = args.get("border", False)
        if border_args:
            border_color = args.get("border_color", "ffffff")
            border_width = args.get("border_width", 2)
            out_width = args.get("width", 1280)
            out_height = args.get("height", 720)
            out_fps = args.get("fps", 30)
            # Wrap the filter with a border
            filter_complex = f"{filter_complex}format=rgba,colorchannelmixer=rr=1.0:gg=1.0:bb=1.0:aa=1.0[out_viz]; "
            filter_complex += f"color=c={border_color}:s={out_width + 2 * border_width}x{out_height + 2 * border_width}:r={out_fps},format=yuva420p[border]; "
            filter_complex += (
                f"[border][out_viz]overlay={border_width}:{border_width}:format=auto[out]"
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
