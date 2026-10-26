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
}

# Valid configuration keys
VALID_KEYS = set(DEFAULT_CONFIG.keys())


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
            for line in f:
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
    # Map of config keys to argparse argument names
    key_map = {
        "resolution": "resolution",
        "format": "format",
        "fps": "fps",
        "preset": "preset",
        "crf": "crf",
        "accel": "accel",
        "mode": "mode",
    }
    
    for config_key, arg_name in key_map.items():
        # Only use config value if argument wasn't explicitly set
        # We check if the value is still the default
        default_value = getattr(args, f"_{arg_name}_default", None)
        current_value = getattr(args, arg_name)
        
        # If current value is the default, use config value
        if current_value == default_value and config_key in config:
            setattr(args, arg_name, config[config_key])
    
    # Handle output directory
    if args.output is None and config.get("output_dir"):
        args.output = config["output_dir"]
    
    return args
