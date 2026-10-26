"""
Audio Visualizer Plugins

Each plugin is a standalone file that defines a VisualizerPlugin subclass.
Plugins are auto-discovered from this directory.
"""

from .base import VisualizerPlugin
from .registry import PluginRegistry

__all__ = ["VisualizerPlugin", "PluginRegistry"]
