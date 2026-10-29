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

        # Range validation (for numeric types); None bound means unbounded
        if self.range is not None and isinstance(value, (int, float)):
            min_val, max_val = self.range
            if (min_val is not None and value < min_val) or (
                max_val is not None and value > max_val
            ):
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
        **kwargs,
    ) -> str:
        """
        Build the ffmpeg filter_complex string for this visualizer.

        Args:
            width: Output video width in pixels
            height: Output video height in pixels
            fps: Frame rate (frames per second)
            options: Validated plugin options dict (from plugin's schema)
            audio_index: Index of the audio input stream in ffmpeg command
            video_index: Index of the background video input
            **kwargs: Additional keyword arguments (colors, bg_color, args, etc.)

        Returns:
            A complete filter_complex string that produces an '[out]' labeled output.
            The filter should consume audio from [audio_index]:a and optionally
            use [video_index]:v as a background.

        Example return value:
            "[0:a] showspectrum=size=1280x720:scale=log[viz]; "
            "[1:v][viz] overlay=shortest=1[out]"
        """
        pass

    # ------------------------------------------------------------------
    #  Hooks — override these instead of build_command()
    # ------------------------------------------------------------------

    def get_inputs(self, args: dict) -> list[list[str]]:
        """
        Return the list of ffmpeg input argument lists.

        Each element is a list of ffmpeg args for one input stream.
        The first element is always the audio input (index 0).

        Default: audio + background color video (index 1).
        Override for plugins that need different inputs (e.g., albumart
        uses an image file, vectorscope needs no background).
        """
        width = args["width"]
        height = args["height"]
        fps = args["fps"]
        bg_color = args.get("bg_color") or "black"
        return [
            ["-i", args["input"]],
            ["-f", "lavfi", "-i", f"color=c={bg_color}:s={width}x{height}:r={fps}"],
        ]

    def get_codec_settings(self, fmt: str, args: dict, accel: str = "sw") -> list:
        """
        Return codec settings for the output.

        Default implementation handles all standard formats and hardware
        acceleration methods. Override to customize encoding.
        """
        return self._get_codec_settings(fmt, args, accel)

    def post_process_filter(self, filter_str: str, args: dict) -> str:
        """
        Modify the filter graph after construction, before encoding.

        Called with the complete filter graph (ending with [out]).
        Return the modified filter graph.

        Default: apply border if enabled.
        """
        if args.get("border"):
            border_color = args.get("border_color", "ffffff")
            border_width = args.get("border_width", 2)
            width = args["width"]
            height = args["height"]
            fps = args["fps"]
            filter_str += "format=rgba,colorchannelmixer=rr=1.0:gg=1.0:bb=1.0:aa=1.0[out_viz]; "
            filter_str += (
                f"color=c={border_color}:s={width + 2 * border_width}x{height + 2 * border_width}:r={fps},"
                "format=yuva420p[border]; "
            )
            filter_str += f"[border][out_viz]overlay={border_width}:{border_width}:format=auto[out]"
        return filter_str

    def get_output_label(self) -> str:
        """Return the output label (default: 'out')."""
        return "out"

    # ------------------------------------------------------------------
    #  Command assembly
    # ------------------------------------------------------------------

    def build_command(self, args: dict) -> list:
        """
        Build the complete ffmpeg command for this plugin.

        Uses the hook methods (get_inputs, get_codec_settings,
        post_process_filter, get_output_label) to assemble the command.
        Override individual hooks rather than this method.

        Args:
            args: Dictionary with all CLI options and plugin-specific values.

        Returns:
            List of ffmpeg command arguments.
        """
        width = args["width"]
        height = args["height"]
        fps = args["fps"]
        colors = args.get("colors")
        bg_color = args.get("bg_color")

        # Extract plugin-specific options from args using the plugin's schema
        schema = self.get_options()
        plugin_options = {}
        for opt in schema.values():
            # Schema names use hyphens (CLI format); args dict uses underscores
            val = args.get(opt.name.replace("-", "_"))
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
            args=args,
        )

        # Post-process (border, etc.)
        filter_complex = self.post_process_filter(filter_complex, args)

        # Assemble command
        cmd = ["ffmpeg", "-y"]
        for input_args in self.get_inputs(args):
            cmd.extend(input_args)

        cmd.extend(["-filter_complex", filter_complex])

        output_label = self.get_output_label()
        cmd.extend(["-map", f"[{output_label}]", "-map", "0:a?"])

        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        cmd.extend(self.get_codec_settings(fmt, args, accel))
        cmd.extend(["-shortest", args["output"]])

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
