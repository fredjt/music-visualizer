"""
Configuration Management

Handles loading, saving, and merging configuration from files.
Configuration is stored in ~/.audio_visualizer/config.yml
"""

import os
from pathlib import Path
from typing import Any

from audio_visualizer.logging_config import logger
from audio_visualizer.visualizers.base import PluginOption

# Environment variable prefix
ENV_PREFIX = "AUDIO_VISUALIZER_"

# Default configuration values
DEFAULT_CONFIG = {
    "resolution": "1280x720",
    "format": "mp4",
    "fps": 30,
    "preset": "medium",
    "crf": 23,
    "accel": "auto",
    "mode": "spectrum",
    "output_dir": None,
    "colors": None,
    "theme": None,
}

# Valid configuration keys
VALID_KEYS = set(DEFAULT_CONFIG.keys())

# Color themes
COLOR_THEMES = {
    "neon": "lime,magenta,cyan,yellow",
    "sunset": "red,orange,yellow,white",
    "ocean": "blue,cyan,teal,white",
    "forest": "green,lime,yellow,white",
    "dark": "purple,blue,gray,white",
    "light": "white,gray,blue,green",
}

# Valid color themes
VALID_THEMES = set(COLOR_THEMES.keys())

# Configuration value validators
CONFIG_VALIDATORS = {
    "resolution": lambda v: isinstance(v, str) and "x" in v,
    "format": lambda v: v in ("mp4", "mkv", "webm", "avi", "mov", "flv"),
    "fps": lambda v: isinstance(v, int) and 1 <= v <= 240,
    "preset": lambda v: (
        v
        in (
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        )
    ),
    "crf": lambda v: isinstance(v, int) and 0 <= v <= 51,
    "accel": lambda v: v in ("auto", "nvenc", "qsv", "vaapi", "disabled"),
    "mode": lambda v: isinstance(v, str) and len(v) > 0,
}


def get_config_dir() -> str:
    """Get the configuration directory path."""
    config_dir = os.path.join(Path.home(), ".audio_visualizer")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_path() -> str:
    """Get the configuration file path."""
    return os.path.join(get_config_dir(), "config.yml")


def load_env_vars() -> dict[str, Any]:
    """
    Load configuration from environment variables.

    Environment variables use the prefix AUDIO_VISUALIZER_ followed by
    the lowercase config key (e.g., AUDIO_VISUALIZER_RESOLUTION, AUDIO_VISUALIZER_FPS).

    Returns:
        Dictionary with configuration values from environment variables
    """
    env_config: dict[str, Any] = {}

    for key in VALID_KEYS:
        env_key = f"{ENV_PREFIX}{key.upper()}"
        value = os.environ.get(env_key)
        if value is not None:
            # Convert types
            if value.lower() in ("true", "false"):
                env_config[key] = value.lower() == "true"
            elif value.isdigit():
                env_config[key] = int(value)
            elif value.replace(".", "", 1).isdigit():
                env_config[key] = float(value)
            else:
                env_config[key] = value

            # Validate the value
            if key in CONFIG_VALIDATORS:
                if not CONFIG_VALIDATORS[key](env_config[key]):
                    logger.warning(f"Invalid value for '{env_key}': {env_config[key]}. Ignoring.")
                    env_config.pop(key, None)

            # Validate theme values
            if key == "theme" and env_config.get(key) is not None:
                if env_config[key] not in VALID_THEMES:
                    logger.warning(f"Invalid theme '{env_config[key]}' in {env_key}. Ignoring.")
                    env_config.pop(key, None)

    return env_config


def _coerce_scalar(value: str) -> Any:
    """Convert a raw config string to a Python scalar (bool/int/float/str)."""
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.isdigit():
        return int(value)
    if value.replace(".", "", 1).isdigit():
        return float(value)
    return value


def _parse_config_file(path: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """
    Parse the simple YAML-like config file (no external dependencies).

    Supports top-level ``key: value`` pairs and one level of nesting:
    ``plugin:`` headers followed by indented ``key: value`` lines, which
    become per-plugin option sections.

    Returns:
        Tuple of (global_values, plugin_sections) with raw string values.
    """
    globals: dict[str, str] = {}
    plugins: dict[str, dict[str, str]] = {}

    with open(path) as f:
        raw_lines = f.readlines()

    i = 0
    n = len(raw_lines)
    while i < n:
        raw = raw_lines[i]
        i += 1
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if raw[0] in (" ", "\t"):
            logger.warning(f"Config: indented line outside a section: {line!r}. Ignoring.")
            continue

        key, sep, value = line.partition(":")
        if not sep:
            logger.warning(f"Config: invalid line (missing ':'): {line!r}. Ignoring.")
            continue
        key = key.strip()
        value = value.strip()

        if value == "":
            # Either a section header (indented lines follow) or an empty value.
            is_section = False
            j = i
            while j < n:
                raw = raw_lines[j]
                j += 1
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                is_section = raw[0] in (" ", "\t")
                break
            if is_section:
                # Section header: consume indented lines. Stop (without
                # consuming) at the next top-level line.
                section: dict[str, str] = {}
                while i < n:
                    raw = raw_lines[i]
                    inner = raw.strip()
                    if not inner or inner.startswith("#"):
                        i += 1
                        continue
                    if raw[0] not in (" ", "\t"):
                        break  # Next top-level key
                    i += 1
                    skey, ssep, sval = inner.partition(":")
                    if not ssep:
                        logger.warning(f"Config: invalid line in '{key}': {inner!r}. Ignoring.")
                        continue
                    section[skey.strip()] = sval.strip()
                plugins[key] = section
            else:
                globals[key] = ""
        else:
            globals[key] = value

    return globals, plugins


def _find_option(
    schema: dict[str, PluginOption], plugin_name: str, key: str
) -> PluginOption | None:
    """Find an option schema entry by full name or by section-shortened name."""
    if key in schema:
        return schema[key]
    for candidate in (f"{plugin_name}-{key}", f"{plugin_name}_{key}"):
        if candidate in schema:
            return schema[candidate]
    return None


def _validate_plugin_sections(
    raw_plugins: dict[str, dict[str, str]], registry: Any | None
) -> dict[str, dict[str, Any]]:
    """
    Validate raw per-plugin config sections against plugin option schemas.

    Unknown plugins/options are skipped with a warning; values are coerced
    and validated via ``PluginOption.validate()`` (type, choices, range).
    """
    validated: dict[str, dict[str, Any]] = {}
    if not raw_plugins:
        return validated

    if registry is None:
        # No schemas available: keep raw values without validation
        return {name: dict(opts) for name, opts in raw_plugins.items()}

    all_plugins = registry.get_all()
    for name, opts in raw_plugins.items():
        plugin_cls = all_plugins.get(name)
        if plugin_cls is None:
            logger.warning(f"Config: unknown plugin section '{name}'. Ignoring.")
            continue
        schema = plugin_cls.get_options()
        clean: dict[str, Any] = {}
        for opt_name, raw_value in opts.items():
            if raw_value == "":
                continue
            opt = _find_option(schema, name, opt_name)
            if opt is None:
                logger.warning(
                    f"Config: plugin '{name}' has unknown option '{opt_name}'. Ignoring."
                )
                continue
            try:
                clean[opt.name] = opt.validate(raw_value)
            except ValueError as e:
                logger.warning(f"Config: {e} Using default.")
        if clean:
            validated[name] = clean

    return validated


def load_config(registry: Any | None = None) -> dict[str, Any]:
    """
    Load configuration from file.

    Global keys are validated against ``CONFIG_VALIDATORS``. Per-plugin
    sections (e.g., ``spectrum:``) are validated against the plugins'
    option schemas when a registry is provided.

    Args:
        registry: Optional PluginRegistry used to validate per-plugin options.

    Returns:
        Dictionary with configuration values. Global keys live at the top
        level; per-plugin options live under the ``"plugins"`` key as
        ``{plugin_name: {option_name: value}}``.
    """
    config_path = get_config_path()

    if not os.path.exists(config_path):
        config = dict(DEFAULT_CONFIG)
        config["plugins"] = {}
        return config

    config = dict(DEFAULT_CONFIG)
    config["plugins"] = {}

    try:
        raw_globals, raw_plugins = _parse_config_file(config_path)
    except Exception as e:
        logger.warning(f"Could not load config file: {e}")
        return config

    for key, value in raw_globals.items():
        if key not in VALID_KEYS:
            logger.warning(f"Config: unknown key '{key}'. Ignoring.")
            continue

        config[key] = _coerce_scalar(value)

        # Validate the value
        if key in CONFIG_VALIDATORS:
            if not CONFIG_VALIDATORS[key](config[key]):
                logger.warning(f"Invalid value for '{key}': {config[key]}. Using default.")
                config[key] = DEFAULT_CONFIG[key]

        # Validate theme values
        if key == "theme" and config[key] is not None:
            if config[key] not in VALID_THEMES:
                logger.warning(f"Invalid theme '{config[key]}'. Using default.")
                config[key] = DEFAULT_CONFIG[key]

    config["plugins"] = _validate_plugin_sections(raw_plugins, registry)

    return config


def _collect_plugin_sections(namespace: Any, registry: Any | None) -> dict[str, dict]:
    """
    Collect non-default plugin option values from a parsed args namespace.

    Returns:
        Dict of {plugin_name: {short_option_name: value}} for options whose
        current value differs from the schema default.
    """
    sections: dict[str, dict] = {}
    if registry is None:
        return sections

    for name, plugin_cls in sorted(registry.get_all().items()):
        schema = plugin_cls.get_options()
        if not schema:
            continue
        opts: dict = {}
        for opt_name, opt in schema.items():
            # Option names already include the plugin prefix (e.g.,
            # "spectrum-mode" -> args.spectrum_mode)
            attr = opt_name.replace("-", "_")
            value = getattr(namespace, attr, None)
            if value is None or value == opt.default:
                continue
            # Store under the section-shortened name (strip plugin prefix)
            short = opt_name
            for prefix in (f"{name}-", f"{name}_"):
                if short.startswith(prefix):
                    short = short[len(prefix) :]
                    break
            opts[short] = value
        if opts:
            sections[name] = opts

    return sections


def save_config(config: dict[str, Any] | Any | None = None, registry: Any | None = None) -> str:
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary or parsed args namespace to save.
            If None, saves the current config file contents. Dictionaries may
            include a ``"plugins"`` key with per-plugin option sections.
        registry: Optional PluginRegistry used to collect plugin option values
            from a namespace.

    Returns:
        Path to the saved config file
    """
    if config is None:
        config = load_config(registry)

    if isinstance(config, dict):
        plugin_sections = config.get("plugins", {})
        global_cfg = {k: v for k, v in config.items() if k != "plugins"}
    else:
        # Parsed args namespace
        global_cfg = {}
        for key in VALID_KEYS:
            attr = "output" if key == "output_dir" else key
            global_cfg[key] = getattr(config, attr, None)
        plugin_sections = _collect_plugin_sections(config, registry)

    config_path = get_config_path()

    with open(config_path, "w") as f:
        f.write("# Audio Visualizer Configuration\n")
        f.write("# Edit this file to set default options\n")
        f.write("# Lines starting with # are comments\n")
        f.write("# Per-plugin sections use indented option names, e.g.:\n")
        f.write("#   spectrum:\n")
        f.write("#     style: scroll\n\n")

        for key, value in global_cfg.items():
            if isinstance(value, bool):
                f.write(f"{key}: {'true' if value else 'false'}\n")
            elif value is None:
                f.write(f"{key}: \n")
            else:
                f.write(f"{key}: {value}\n")

        for plugin_name in sorted(plugin_sections):
            opts = plugin_sections[plugin_name]
            if not opts:
                continue
            f.write(f"\n# {plugin_name} options\n")
            f.write(f"{plugin_name}:\n")
            for opt_name, value in opts.items():
                if isinstance(value, bool):
                    f.write(f"  {opt_name}: {'true' if value else 'false'}\n")
                else:
                    f.write(f"  {opt_name}: {value}\n")

    return config_path


def merge_config(
    args: Any,
    config: dict[str, Any],
    env_vars: dict[str, Any] | None = None,
    registry: Any | None = None,
) -> Any:
    """
    Merge command-line arguments with configuration file and environment variable values.
    Precedence (highest to lowest): CLI args > environment variables > config file > defaults.

    Args:
        args: Parsed command-line arguments namespace
        config: Configuration dictionary from file
        env_vars: Configuration dictionary from environment variables. If None, loads from env.
        registry: Optional PluginRegistry used to apply per-plugin option sections
            (values from ``config["plugins"]`` are applied when the matching CLI
            arg is at its schema default).

    Returns:
        Updated args namespace
    """
    if env_vars is None:
        env_vars = load_env_vars()

    # Map of config keys to argparse argument names and their defaults
    key_map = {
        "resolution": ("resolution", "1280x720"),
        "format": ("format", "mp4"),
        "fps": ("fps", 30),
        "preset": ("preset", "medium"),
        "crf": ("crf", 23),
        "accel": ("accel", "auto"),
        "mode": ("mode", "spectrum"),
        "colors": ("colors", None),
        "theme": ("theme", None),
    }

    for config_key, (arg_name, default_value) in key_map.items():
        current_value = getattr(args, arg_name, None)

        # If current value is the default, check env vars first, then config file
        if current_value == default_value:
            if config_key in env_vars:
                setattr(args, arg_name, env_vars[config_key])
            elif config_key in config:
                setattr(args, arg_name, config[config_key])

    # Handle output directory (CLI > env > config)
    if args.output is None:
        env_output = env_vars.get("output_dir") or os.environ.get(f"{ENV_PREFIX}OUTPUT_DIR")
        if env_output:
            args.output = env_output
        elif config.get("output_dir"):
            args.output = config["output_dir"]

    # Handle theme (resolve to colors)
    # Precedence: CLI theme > env theme > config theme
    if getattr(args, "colors", None) is None:
        theme = getattr(args, "theme", None)
        # Check env var for theme if CLI didn't set it
        if theme is None:
            env_theme = env_vars.get("theme") or os.environ.get(f"{ENV_PREFIX}THEME")
            if env_theme:
                theme = env_theme
        # Fall back to config theme
        if theme is None:
            theme = config.get("theme")
        if theme and theme in COLOR_THEMES:
            args.colors = COLOR_THEMES[theme]

    # Apply per-plugin option sections (config file > defaults, CLI wins)
    plugin_sections = config.get("plugins") or {}
    if plugin_sections and registry is not None:
        all_plugins = registry.get_all()
        for plugin_name, opts in plugin_sections.items():
            plugin_cls = all_plugins.get(plugin_name)
            if plugin_cls is None:
                continue
            schema = plugin_cls.get_options()
            for opt_key, value in opts.items():
                opt = _find_option(schema, plugin_name, opt_key)
                if opt is None:
                    continue
                # Option names already include the plugin prefix
                attr = opt.name.replace("-", "_")
                current = getattr(args, attr, None)
                if current is None or current == opt.default:
                    setattr(args, attr, value)

    return args


# Validation rules: (condition, error_msg, warning_msg)
VALIDATION_RULES = [
    # Hardware encoding remaps CRF onto the encoder's own quality scale
    (
        lambda c: c.get("accel") not in ("auto", "disabled") and c.get("crf") is not None,
        None,
        "Hardware encoding ({accel}) remaps CRF {crf} to its own quality scale (CQ for NVENC, global_quality/qscale for QSV/VA-API).",
    ),
    # Very high FPS with ultrafast preset
    (
        lambda c: c.get("fps", 30) > 60 and c.get("preset") == "ultrafast",
        None,
        "High FPS ({fps}) with ultrafast preset may produce large files. Consider medium preset for better quality.",
    ),
    # Ultrafast preset with high CRF (waste of CPU)
    (
        lambda c: c.get("crf", 23) < 18 and c.get("preset") in ("ultrafast", "superfast"),
        None,
        "Low CRF ({crf}) with {preset} preset wastes CPU. Use slow/slower for better compression.",
    ),
    # WebM with libx264 (should use libvpx)
    (
        lambda c: c.get("format") == "webm" and c.get("accel") in ("auto", "disabled"),
        None,
        "WebM format works best with VP9 codec. Ensure you're not using h264_nvenc/qsv/vaapi.",
    ),
]


def validate_config(config: dict[str, Any], args: Any) -> list[str]:
    """
    Validate the merged configuration and return a list of warnings/errors.

    Checks for incompatible combinations and suboptimal settings.

    Args:
        config: Configuration dictionary from file
        args: Merged command-line arguments namespace

    Returns:
        List of warning/error messages (empty if no issues)
    """
    # Build a combined config dict with final values
    merged = dict(config)
    for key in DEFAULT_CONFIG:
        arg_name = key if key != "output_dir" else "output"
        value = getattr(args, arg_name, None)
        if value is not None:
            merged[key] = value

    issues = []

    for condition, error_msg, warning_msg in VALIDATION_RULES:
        if condition(merged):
            if error_msg:
                issues.append(f"ERROR: {error_msg.format(**merged)}")
            elif warning_msg:
                issues.append(f"WARNING: {warning_msg.format(**merged)}")

    return issues


def validate_config_only(config: dict[str, Any]) -> list[str]:
    """
    Validate the config file values without CLI args.

    Args:
        config: Configuration dictionary from file

    Returns:
        List of warning/error messages
    """
    return validate_config(config, type("Args", (), {k: None for k in DEFAULT_CONFIG})())


# Visualizer preset configuration
# These are saved per-visualizer for --visualizer-config support
VISUALIZER_PRESETS_DIR = os.path.join(get_config_dir(), "presets")


def get_preset_path(name: str) -> str:
    """Get the preset file path for a visualizer."""
    os.makedirs(VISUALIZER_PRESETS_DIR, exist_ok=True)
    return os.path.join(VISUALIZER_PRESETS_DIR, f"{name}.json")


def save_visualizer_preset(name: str, preset: dict) -> str:
    """
    Save a visualizer preset to a JSON file.

    Args:
        name: Visualizer name (e.g., 'spectrum', 'waveform')
        preset: Dictionary of preset values

    Returns:
        Path to the saved preset file
    """
    import json

    os.makedirs(VISUALIZER_PRESETS_DIR, exist_ok=True)
    preset_path = get_preset_path(name)
    with open(preset_path, "w") as f:
        json.dump(preset, f, indent=2)
    return preset_path


def load_visualizer_preset(name: str) -> dict | None:
    """
    Load a visualizer preset from a JSON file.

    Args:
        name: Visualizer name (e.g., 'spectrum', 'waveform')

    Returns:
        Dictionary of preset values, or None if not found
    """
    import json

    preset_path = get_preset_path(name)
    if not os.path.exists(preset_path):
        return None
    try:
        with open(preset_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_visualizer_presets() -> list[str]:
    """
    List all available visualizer presets.

    Returns:
        List of preset names (visualizer names)
    """
    if not os.path.isdir(VISUALIZER_PRESETS_DIR):
        return []
    return [
        os.path.splitext(f)[0] for f in os.listdir(VISUALIZER_PRESETS_DIR) if f.endswith(".json")
    ]
