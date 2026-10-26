"""
Configuration Management

Handles loading, saving, and merging configuration from files.
Configuration is stored in ~/.audio_visualizer/config.yml
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional


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

# Valid color themes
VALID_THEMES = set(COLOR_THEMES.keys())

# Color themes
COLOR_THEMES = {
    "neon": "lime,magenta,cyan,yellow",
    "sunset": "red,orange,yellow,white",
    "ocean": "blue,cyan,teal,white",
    "forest": "green,lime,yellow,white",
    "dark": "purple,blue,gray,white",
    "light": "white,gray,blue,green",
}

# Configuration value validators
CONFIG_VALIDATORS = {
    "resolution": lambda v: isinstance(v, str) and 'x' in v,
    "format": lambda v: v in ('mp4', 'mkv', 'webm', 'avi', 'mov', 'flv'),
    "fps": lambda v: isinstance(v, int) and 1 <= v <= 240,
    "preset": lambda v: v in ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'),
    "crf": lambda v: isinstance(v, int) and 0 <= v <= 51,
    "accel": lambda v: v in ('auto', 'nvenc', 'qsv', 'vaapi', 'disabled'),
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


def load_config() -> Dict[str, Any]:
    """
    Load configuration from file.
    
    Returns:
        Dictionary with configuration values
    """
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return dict(DEFAULT_CONFIG)
    
    config = dict(DEFAULT_CONFIG)
    
    try:
        # Simple YAML-like parsing (no external dependencies)
        with open(config_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key in VALID_KEYS:
                        # Convert types
                        if value.lower() in ('true', 'false'):
                            config[key] = value.lower() == 'true'
                        elif value.isdigit():
                            config[key] = int(value)
                        elif value.replace('.', '', 1).isdigit():
                            config[key] = float(value)
                        else:
                            config[key] = value
                        
                        # Validate the value
                        if key in CONFIG_VALIDATORS:
                            if not CONFIG_VALIDATORS[key](config[key]):
                                print(f"Warning: Invalid value for '{key}' on line {line_num}: {config[key]}. Using default.")
                                config[key] = DEFAULT_CONFIG[key]
                        
                        # Validate theme values
                        if key == "theme" and config[key] is not None:
                            if config[key] not in VALID_THEMES:
                                print(f"Warning: Invalid theme '{config[key]}' on line {line_num}. Using default.")
                                config[key] = DEFAULT_CONFIG[key]
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
    
    return config


def save_config(config: Optional[Dict[str, Any]] = None) -> str:
    """
    Save configuration to file.
    
    Args:
        config: Configuration dictionary to save. If None, saves current config.
    
    Returns:
        Path to the saved config file
    """
    if config is None:
        config = load_config()
    
    config_path = get_config_path()
    
    with open(config_path, 'w') as f:
        f.write("# Audio Visualizer Configuration\n")
        f.write("# Edit this file to set default options\n")
        f.write("# Lines starting with # are comments\n\n")
        
        for key, value in config.items():
            if isinstance(value, bool):
                f.write(f"{key}: {'true' if value else 'false'}\n")
            elif value is None:
                f.write(f"{key}: \n")
            else:
                f.write(f"{key}: {value}\n")
    
    return config_path


def merge_config(args: Any, config: Dict[str, Any]) -> Any:
    """
    Merge command-line arguments with configuration file values.
    Command-line arguments take precedence.
    
    Args:
        args: Parsed command-line arguments namespace
        config: Configuration dictionary
    
    Returns:
        Updated args namespace
    """
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
        # Only use config value if argument wasn't explicitly set
        current_value = getattr(args, arg_name, None)
        
        # If current value is the default, use config value
        if current_value == default_value and config_key in config:
            setattr(args, arg_name, config[config_key])
    
    # Handle output directory
    if args.output is None and config.get("output_dir"):
        args.output = config["output_dir"]
    
    # Handle theme (resolve to colors)
    if getattr(args, "colors", None) is None and config.get("theme"):
        theme = config["theme"]
        if theme in COLOR_THEMES:
            args.colors = COLOR_THEMES[theme]
    
    return args
