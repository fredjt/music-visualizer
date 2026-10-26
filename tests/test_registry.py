"""Tests for plugin registry."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from audio_visualizer.visualizers.registry import PluginRegistry
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def test_load_all_built_in_plugins(self):
        """Test loading built-in plugins."""
        registry = PluginRegistry()
        count = registry.load_all()
        assert count > 0
        assert "spectrum" in registry.get_all()

    def test_get_plugin_by_name(self):
        """Test getting a plugin by name."""
        registry = PluginRegistry()
        registry.load_all()
        plugin = registry.get("spectrum")
        assert plugin is not None
        assert issubclass(plugin, VisualizerPlugin)

    def test_get_nonexistent_plugin(self):
        """Test getting a nonexistent plugin returns None."""
        registry = PluginRegistry()
        registry.load_all()
        plugin = registry.get("nonexistent")
        assert plugin is None

    def test_list_plugins(self):
        """Test listing plugins."""
        registry = PluginRegistry()
        registry.load_all()
        plugins = registry.list_plugins()
        assert len(plugins) > 0
        assert "name" in plugins[0]
        assert "display_name" in plugins[0]

    def test_get_metadata(self):
        """Test getting plugin metadata."""
        registry = PluginRegistry()
        registry.load_all()
        meta = registry.get_metadata("spectrum")
        assert meta is not None
        assert meta.name == "spectrum"
        assert meta.display_name == "Color Spectrum"

    def test_user_plugin_directory(self, tmp_path):
        """Test loading user plugins from custom directory."""
        # Create a test plugin
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata

class TestPlugin(VisualizerPlugin):
    metadata = PluginMetadata(
        name="test",
        display_name="Test Plugin",
        description="A test plugin",
    )
    
    def build_filter(self, width, height, fps, audio_index=0, video_index=1):
        return f"[{audio_index}:a] testfilter[size={width}x{height}][out]"
""")
        
        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        count = registry.load_all()
        assert count > 0
        assert "test" in registry.get_all()
