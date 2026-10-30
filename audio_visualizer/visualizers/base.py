"""
Base Visualizer Plugin

All visualizer plugins must inherit from this class and implement
defined methods. The core system uses these interfaces to build
ffmpeg filter graphs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .utils import build_background


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
    choices: list[Any] | None = None  # Allowed values (optional)
    range: tuple[float | None, float | None] | None = None  # (min, max) numeric range (optional)
    group: str | None = None  # Option group for CLI organization (optional)

    def validate(self, value: Any) -> Any:
        """Validate and coerce a value to the option's type.

        Returns the validated/coerced value.
        Raises ValueError if validation fails.
        """
        if value is None:
            return self.default

        # Boolean strings (config files store values as text)
        if self.type is bool and isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "yes", "1", "on"):
                return True
            if low in ("false", "no", "0", "off"):
                return False
            raise ValueError(f"Option '{self.name}': expected bool, got '{value}'")

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
                return f"[{audio_index}:a] myfilter=size={width}x{height}[viz]"

    The base class composes the final '[out]' stream from the plugin's
    main output (see compose_final_filter()) and applies post-processing
    such as the border. Plugins should NOT produce the final '[out]'
    label themselves.
    """

    # Override these with plugin metadata and options
    metadata: PluginMetadata | None = None
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
    def validate_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        """Validate and coerce options against the plugin's schema.

        Returns a dict with validated/coerced values.
        Options not in the schema are passed through unchanged.
        Missing options get their default values.
        """
        validated: dict[str, Any] = {}
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
        options: dict[str, Any],
        **kwargs: Any,
    ) -> str | dict[str, str]:
        """
        Build the ffmpeg filter graph for this visualizer.

        The returned graph must produce the plugin's main output labeled
        with get_output_label(options) (default: 'viz'). It must NOT
        produce the final '[out]' label — the base class composes that
        via compose_final_filter() and then applies post-processing
        (border, etc.) via post_process_filter().

        Args:
            width: Output video width in pixels
            height: Output video height in pixels
            fps: Frame rate (frames per second)
            options: Validated plugin options dict (from plugin's schema)
            **kwargs: Additional keyword arguments. The base class passes
                 colors, bg_color, and the full args dict; input stream
                 indices are available as audio_index/video_index keys in
                 args (plugins may also declare them as keyword params).

        Returns:
            str: A filter graph producing the main output label.
                 Example: "[0:a] showspectrum=size=1280x720:scale=log[viz]"
            dict[str, str]: Multi-output support — maps output names to
                 filter segments. Segments are joined with '; ' and the
                 first key is the main output label.
        """
        pass

    # ------------------------------------------------------------------
    #  Hooks — override these instead of build_command()
    # ------------------------------------------------------------------

    def get_inputs(self, args: dict[str, Any]) -> list[list[str]]:
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

    def get_codec_settings(self, fmt: str, args: dict[str, Any], accel: str = "sw") -> list[str]:
        """
        Return codec settings for the output.

        Default implementation handles all standard formats and hardware
        acceleration methods. Override to customize encoding.
        """
        return self._get_codec_settings(fmt, args, accel)

    def post_process_filter(self, filter_str: str, args: dict[str, Any]) -> str:
        """
        Modify the filter graph after construction, before encoding.

        Called with the complete filter graph (ending with [out]).
        Return the modified filter graph.

        Default: apply border if enabled. The border chain consumes the
        current [out] pad and produces a new final [out] (ffmpeg allows a
        label to be produced, consumed, and produced again).
        """
        if args.get("border"):
            border_color = args.get("border_color", "ffffff")
            border_width = args.get("border_width", 2)
            width = args["width"]
            height = args["height"]
            fps = args["fps"]
            graph = filter_str.strip().rstrip(";")
            graph += (
                f"; [out]format=rgba,colorchannelmixer=rr=1.0:gg=1.0:bb=1.0:aa=1.0[out_viz]; "
                f"color=c={border_color}:s={width + 2 * border_width}x{height + 2 * border_width}:r={fps},"
                "format=yuva420p[border]; "
            )
            graph += f"[border][out_viz]overlay={border_width}:{border_width}:format=auto[out]"
            return graph
        return filter_str

    def get_output_label(self, options: dict[str, Any]) -> str:
        """Return the label of the main output produced by build_filter().

        The base class uses this label to compose the final [out] stream.
        Override for plugins whose main output uses a different label, or
        where the label depends on options (e.g., spectrogram's transpose
        mode produces the final frame from [transposed]).

        Default: 'viz'.
        """
        return "viz"

    def get_bg_opacity(self, args: dict[str, Any]) -> float:
        """Return the background opacity when --bg-color is not set.

        Used by the default compose_final_filter(). Default: 0.3.
        """
        return 0.3

    def compose_final_filter(self, filter_str: str, main_label: str, args: dict[str, Any]) -> str:
        """
        Compose the final filter graph (ending with [out]) from the
        plugin's filter graph.

        Called after build_filter() and before post_process_filter().

        Args:
            filter_str: The plugin's filter graph. Its main output is
                        labeled `main_label` (from get_output_label()).
            main_label: Label of the plugin's main output.
            args: Full arguments dict.

        Default: if the plugin declares a background input (a second
        input in get_inputs()), the main output is overlaid on that
        background; otherwise the main output is relabeled to [out].

        The background input index defaults to 1 (the standard layout);
        the composite visualizer passes ``args["bg_index"]`` when a sub-mode's
        background sits at a different position in the input list.
        """
        graph = filter_str.strip()
        if not graph.endswith(";"):
            graph += ";"

        inputs = self.get_inputs(args)
        if len(inputs) > 1:
            bg_color = args.get("bg_color")
            bg_index = args.get("bg_index", 1)
            bg_filter = build_background(bg_index, bg_color, opacity=self.get_bg_opacity(args))
            return f"{graph} {bg_filter}[bg][{main_label}] overlay=shortest=1:format=auto[out]"

        return f"{graph} [{main_label}]format=yuv420p[out]"

    # ------------------------------------------------------------------
    #  Command assembly
    # ------------------------------------------------------------------

    def build_filter_complex(self, args: dict[str, Any]) -> str:
        """
        Run the full filter pipeline and return the final filter_complex
        string (ending with [out]).

        Pipeline:
        1. Extract and validate plugin options from args (schema-driven)
        2. build_filter() — the plugin's filter graph (str or dict of
           segments for multi-output)
        3. compose_final_filter() — produce the final [out] (skipped if
           the graph already ends with [out], e.g. legacy v1.x plugins)
        4. post_process_filter() — border and other post-processing

        Args:
            args: Dictionary with all CLI options and plugin-specific values.

        Returns:
            The final filter_complex string ending with an [out] label.
        """
        if self.metadata is None:
            raise NotImplementedError(
                f"{type(self).__name__} must define a 'metadata' class attribute"
            )
        width = args["width"]
        height = args["height"]
        fps = args["fps"]
        colors = args.get("colors")
        bg_color = args.get("bg_color")

        # Extract plugin-specific options from args using the plugin's schema
        schema = self.get_options()
        plugin_options: dict[str, Any] = {}
        for opt in schema.values():
            # Schema names use hyphens (CLI format); args dict uses underscores
            val = args.get(opt.name.replace("-", "_"))
            if val is not None:
                plugin_options[opt.name] = val

        # Validate options against schema (applies defaults for missing options)
        plugin_options = self.validate_options(plugin_options)

        # Build filter graph
        raw = self.build_filter(
            width=width,
            height=height,
            fps=fps,
            options=plugin_options,
            colors=colors,
            bg_color=bg_color,
            args=args,
        )

        # Normalize: a dict return means multi-output (first key is the main label)
        if isinstance(raw, dict):
            if not raw:
                raise ValueError(
                    f"Plugin '{self.metadata.name}': build_filter() returned an empty dict"
                )
            main_label = next(iter(raw))
            segments = [seg.strip().rstrip(";") for seg in raw.values()]
            filter_complex = "; ".join(segments)
        else:
            main_label = self.get_output_label(plugin_options)
            filter_complex = raw

        # Compose the final [out]. Legacy v1.x plugins (and any plugin
        # whose graph already ends with [out]) are passed through as-is.
        if not filter_complex.strip().rstrip(";").strip().endswith("[out]"):
            filter_complex = self.compose_final_filter(filter_complex, main_label, args)

        # Post-process (border, etc.)
        return self.post_process_filter(filter_complex, args)

    def build_command(self, args: dict[str, Any]) -> list[str]:
        """
        Build the complete ffmpeg command for this plugin.

        Uses the hook methods (get_inputs, get_codec_settings,
        compose_final_filter, post_process_filter) to assemble the
        command. Override individual hooks rather than this method.

        Args:
            args: Dictionary with all CLI options and plugin-specific values.

        Returns:
            List of ffmpeg command arguments.
        """
        # Build filter graph (options, composition, post-processing)
        filter_complex = self.build_filter_complex(args)

        # Assemble command
        cmd = ["ffmpeg", "-y"]
        for input_args in self.get_inputs(args):
            cmd.extend(input_args)

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[out]", "-map", "0:a?"])
        cmd.extend(self._get_metadata_args(args))

        fmt = args.get("format", "mp4")
        accel = args.get("accel", "sw")
        cmd.extend(self.get_codec_settings(fmt, args, accel))
        cmd.extend(["-shortest", args["output"]])

        return cmd

    def _get_metadata_args(self, args: dict[str, Any]) -> list[str]:
        """
        Build ffmpeg args for the output container's metadata.

        Default: copy the source file's tags (title, artist, album,
        comment, ...) into the output container so the video keeps the
        audio's identity, then apply the user's --title/--artist/--album/
        --comment overrides (later -metadata entries win over the copied
        tags). --no-metadata strips all tags for a clean output.
        """
        if args.get("no_metadata"):
            return ["-map_metadata", "-1"]
        meta_args = ["-map_metadata", "0"]
        for key in ("title", "artist", "album", "comment"):
            value = args.get(key)
            if value:
                meta_args.extend(["-metadata", f"{key}={value}"])
        return meta_args

    def _get_codec_settings(self, fmt: str, args: dict[str, Any], accel: str = "sw") -> list[str]:
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
        hw_settings: dict[str, dict[str, Any]] = {
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
                # QSV uses global_quality scale (1-31, lower=better); map the
                # CRF onto it directly (lower CRF = lower global_quality =
                # better quality)
                "extra": [
                    "-movflags",
                    "+faststart",
                    "-global_quality",
                    str(min(max(crf, 1), 31)),
                ],
            },
            "vaapi": {
                "vcodec": "h264_vaapi",
                "pix_fmt": "nv12",
                # VA-API uses qscale (1-31, lower=better); same mapping as QSV
                "extra": ["-movflags", "+faststart", "-q", str(min(max(crf, 1), 31))],
            },
        }

        # Complete mapping of every x264 preset name to the name each
        # hardware encoder accepts. An unmapped name omits -preset;
        # h264_vaapi has no preset option at all (empty table).
        hw_preset_map = {
            "nvenc": {
                "ultrafast": "p1",
                "superfast": "p1",
                "veryfast": "p2",
                "faster": "p3",
                "fast": "fast",
                "medium": "medium",
                "slow": "slow",
                "slower": "p6",
                "veryslow": "p7",
            },
            "qsv": {
                "ultrafast": "veryfast",
                "superfast": "veryfast",
                "veryfast": "veryfast",
                "faster": "faster",
                "fast": "fast",
                "medium": "medium",
                "slow": "slow",
                "slower": "slower",
                "veryslow": "veryslow",
            },
            "vaapi": {},
        }

        # Software encoding settings
        sw_format_codecs: dict[str, dict[str, Any]] = {
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
            cmd = ["-c:v", settings["vcodec"], "-pix_fmt", settings["pix_fmt"]]
            if accel in hw_preset_map:
                hw_preset = hw_preset_map[accel].get(preset)
            else:
                hw_preset = preset
            if hw_preset:
                cmd += ["-preset", hw_preset]
            return cmd + settings["extra"]
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
