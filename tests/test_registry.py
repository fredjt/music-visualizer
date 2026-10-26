"""Tests for plugin registry."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_visualizer.visualizers.base import VisualizerPlugin
from audio_visualizer.visualizers.registry import PluginRegistry


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def test_load_all_built_in_plugins(self):
        """Test loading built-in plugins."""
        registry = PluginRegistry()
        count = registry.load_all()
        assert count > 0
        assert "spectrum" in registry.get_all()

    def test_load_builtin_failure_raises(self):
        """Test that built-in plugin load failure raises RuntimeError."""
        registry = PluginRegistry()

        # Mock import_module to raise an error
        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Mock error")
            with pytest.raises(RuntimeError) as exc_info:
                registry._load_from_package()
            # Check that the error message includes the plugin name and error
            assert "Failed to load built-in plugin" in str(exc_info.value)
            assert "Mock error" in str(exc_info.value)
            # Check that the original exception is chained
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, ImportError)

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


class TestRegistryInstallUninstall:
    """Test plugin installation and uninstallation."""

    def test_install_from_file(self, tmp_path):
        """Test installing a plugin from a file."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        src = Path(__file__).parent / "assets" / "test_plugin.py"
        registry = PluginRegistry(user_plugin_dir=user_dir)
        result = registry.install_from_file(str(src))
        assert result is True
        assert (Path(user_dir) / "test_plugin.py").exists()

    def test_install_from_file_invalid_path(self, tmp_path):
        """Test installing from a non-existent file."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)
        registry = PluginRegistry(user_plugin_dir=user_dir)
        result = registry.install_from_file("/nonexistent/path/plugin.py")
        assert result is False

    def test_uninstall_by_name(self, tmp_path):
        """Test uninstalling a plugin by name."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        src = Path(__file__).parent / "assets" / "test_plugin.py"
        registry = PluginRegistry(user_plugin_dir=user_dir)
        registry.install_from_file(str(src))
        registry.load_all()

        result = registry.uninstall("test")
        assert result is True
        assert not (Path(user_dir) / "test_plugin.py").exists()

    def test_uninstall_nonexistent(self, tmp_path):
        """Test uninstalling a plugin that doesn't exist."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)
        registry = PluginRegistry(user_plugin_dir=user_dir)
        result = registry.uninstall("nonexistent")
        assert result is False

    def test_uninstall_removes_from_registry(self, tmp_path):
        """Test that uninstall removes plugin from registry."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        src = Path(__file__).parent / "assets" / "test_plugin.py"
        registry = PluginRegistry(user_plugin_dir=user_dir)
        registry.install_from_file(str(src))
        registry.load_all()
        assert "test" in registry.get_all()

        registry.uninstall("test")
        # Re-create registry to get fresh state
        registry2 = PluginRegistry(user_plugin_dir=user_dir)
        registry2.load_all()
        assert "test" not in registry2.get_all()

    def test_install_duplicate_plugin(self, tmp_path):
        """Test that installing a duplicate plugin overwrites."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        src = Path(__file__).parent / "assets" / "test_plugin.py"
        registry = PluginRegistry(user_plugin_dir=user_dir)

        # Install once
        result1 = registry.install_from_file(str(src))
        assert result1 is True

        # Install again (should overwrite)
        result2 = registry.install_from_file(str(src))
        assert result2 is True
        assert (Path(user_dir) / "test_plugin.py").exists()


class TestUserPluginLoadingFailure:
    """Test that user plugin loading failures are handled gracefully."""

    def test_load_user_plugin_syntax_error(self, tmp_path, capsys):
        """Test that a user plugin with a syntax error is skipped with a warning."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        # Create a plugin file with a syntax error
        bad_plugin = Path(user_dir) / "bad_plugin.py"
        bad_plugin.write_text("this is not valid python {{{")

        registry = PluginRegistry(user_plugin_dir=user_dir)
        count = registry.load_all()

        # Should still succeed but skip the bad plugin
        assert count >= 0
        captured = capsys.readouterr()
        assert "Warning: Failed to load user plugin 'bad_plugin'" in captured.out
        assert "invalid syntax" in captured.out
        assert "skipped" in captured.out.lower()

    def test_load_user_plugin_missing_base_class(self, tmp_path, capsys):
        """Test that a user plugin without VisualizerPlugin is skipped."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        # Create a plugin file that doesn't define a VisualizerPlugin subclass
        bad_plugin = Path(user_dir) / "not_a_plugin.py"
        bad_plugin.write_text("x = 42\n")

        registry = PluginRegistry(user_plugin_dir=user_dir)
        count = registry.load_all()

        # Should succeed with no plugins loaded from user dir
        assert count >= 0
        captured = capsys.readouterr()
        # No warning expected since there's no error, just no valid plugin
        assert "Warning" not in captured.out

    def test_load_user_plugin_import_error(self, tmp_path, capsys):
        """Test that a user plugin with an import error is skipped with a warning."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        # Create a plugin that imports a non-existent module
        bad_plugin = Path(user_dir) / "import_error_plugin.py"
        bad_plugin.write_text(
            "from nonexistent_module_xyz import something\nclass MyPlugin:\n    pass\n"
        )

        registry = PluginRegistry(user_plugin_dir=user_dir)
        registry.load_all()

        captured = capsys.readouterr()
        assert "Warning: Failed to load user plugin 'import_error_plugin'" in captured.out
        assert "No module named" in captured.out

    def test_load_user_plugin_invalid_metadata(self, tmp_path, capsys):
        """Test that a user plugin with invalid metadata is skipped."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        # Create a plugin that inherits from VisualizerPlugin but has broken metadata
        bad_plugin = Path(user_dir) / "bad_metadata_plugin.py"
        bad_plugin.write_text(
            "from audio_visualizer.visualizers.base import VisualizerPlugin\n"
            "\n"
            "class BadMetadataPlugin(VisualizerPlugin):\n"
            "    @classmethod\n"
            "    def get_metadata(cls):\n"
            "        # Return None to simulate broken metadata\n"
            "        return None\n"
            "\n"
            "    def build_filter(self, audio_data, width, height):\n"
            "        return ''\n"
        )

        registry = PluginRegistry(user_plugin_dir=user_dir)
        registry.load_all()

        captured = capsys.readouterr()
        assert "Warning: Failed to load user plugin 'bad_metadata_plugin'" in captured.out

    def test_install_from_file_nonexistent_source(self, tmp_path, capsys):
        """Test that installing from a nonexistent file returns False."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        registry = PluginRegistry(user_plugin_dir=user_dir)
        result = registry.install_from_file("/nonexistent/path/plugin.py")
        assert result is False
        captured = capsys.readouterr()
        assert "Error installing plugin to" in captured.out
