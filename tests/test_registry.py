"""Tests for plugin registry."""

import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_visualizer.visualizers.base import VisualizerPlugin
from audio_visualizer.visualizers.registry import (
    ORIGIN_BUILTIN,
    ORIGIN_ENTRYPOINT,
    ORIGIN_INSTALLED,
    ORIGIN_PATH,
    PluginRegistry,
)


def _plugin_source(cls: str, name: str, display: str) -> str:
    """Generate the source of a minimal valid external plugin module."""
    return (
        "from audio_visualizer.visualizers.base import ("
        "PluginMetadata, PluginOption, VisualizerPlugin)\n"
        "\n"
        "\n"
        f"class {cls}(VisualizerPlugin):\n"
        "    metadata = PluginMetadata(\n"
        f'        name="{name}",\n'
        f'        display_name="{display}",\n'
        '        description="External test plugin",\n'
        '        version="9.9.9",\n'
        "    )\n"
        '    options = [PluginOption("ext-opt", str, "x", "External option")]\n'
        "\n"
        "    def build_filter(self, width, height, fps, options, audio_index=0,\n"
        "                     video_index=1, colors=None, bg_color=None, args=None):\n"
        '        return f"[{audio_index}:a] testext[size={width}x{height}][viz]"\n'
    )


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
        assert "category" in plugins[0]

    def test_list_plugins_by_category(self):
        """Test filtering plugins by category."""
        registry = PluginRegistry()
        registry.load_all()
        all_plugins = registry.list_plugins()
        spectrum_plugins = registry.list_plugins(category="spectrum")
        assert len(spectrum_plugins) > 0
        assert len(spectrum_plugins) < len(all_plugins)
        assert all(p["category"] == "spectrum" for p in spectrum_plugins)

    def test_list_plugins_unknown_category(self):
        """Test that an unknown category returns an empty list."""
        registry = PluginRegistry()
        registry.load_all()
        assert registry.list_plugins(category="nonexistent") == []

    def test_get_categories(self):
        """Test getting unique plugin categories."""
        registry = PluginRegistry()
        registry.load_all()
        categories = registry.get_categories()
        assert "spectrum" in categories
        assert "meter" in categories
        # Categories should be sorted and unique
        assert categories == sorted(set(categories))

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

    def build_filter(self, width, height, fps, options, audio_index=0, video_index=1):
        return f"[{audio_index}:a] testfilter[size={width}x{height}][viz]"
""")

        registry = PluginRegistry(user_plugin_dir=str(tmp_path))
        count = registry.load_all()
        assert count > 0
        assert "test" in registry.get_all()


class TestPluginOrigins:
    """Test origin tracking for every discovery source."""

    def test_builtin_origin(self):
        """Built-in plugins are tracked as 'builtin' and exposed in listings."""
        registry = PluginRegistry()
        registry.load_all()
        assert registry.get_origin("spectrum") == ORIGIN_BUILTIN
        plugins = registry.list_plugins()
        assert plugins
        assert all(p["origin"] == ORIGIN_BUILTIN for p in plugins)

    def test_path_origin_from_file(self, tmp_path):
        """A plugin file passed via plugin_paths is tracked as 'path'."""
        plugin_file = tmp_path / "ext_plugin.py"
        plugin_file.write_text(_plugin_source("ExtPlugin", "ext", "Ext Plugin"))
        registry = PluginRegistry(plugin_paths=[str(plugin_file)])
        registry.load_all()
        assert "ext" in registry.get_all()
        assert registry.get_origin("ext") == ORIGIN_PATH
        ext = [p for p in registry.list_plugins() if p["name"] == "ext"]
        assert ext and ext[0]["origin"] == ORIGIN_PATH

    def test_path_origin_from_directory(self, tmp_path):
        """Plugins in a plugin_paths directory are tracked as 'path'."""
        (tmp_path / "a_plugin.py").write_text(_plugin_source("APlugin", "exta", "A Plugin"))
        registry = PluginRegistry(plugin_paths=[str(tmp_path)])
        registry.load_all()
        assert registry.get_origin("exta") == ORIGIN_PATH

    def test_installed_origin(self, tmp_path, monkeypatch):
        """Plugins in ~/.audio_visualizer/plugins are tracked as 'installed'."""
        home = tmp_path / "home"
        plugin_dir = home / ".audio_visualizer" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "inst_plugin.py").write_text(
            _plugin_source("InstPlugin", "exti", "Inst Plugin")
        )
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("USERPROFILE", str(home))
        registry = PluginRegistry()
        registry.load_all()
        assert registry.get_origin("exti") == ORIGIN_INSTALLED

    def test_missing_plugin_path_warns(self, tmp_path, caplog):
        """A nonexistent plugin path is skipped with a warning."""
        registry = PluginRegistry(plugin_paths=[str(tmp_path / "does_not_exist")])
        registry.load_all()
        assert "does not exist" in caplog.text
        # Built-ins still load
        assert registry.get("spectrum") is not None

    def test_non_python_plugin_path_warns(self, tmp_path, caplog):
        """A non-.py plugin path is skipped with a warning."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a plugin")
        registry = PluginRegistry(plugin_paths=[str(txt_file)])
        registry.load_all()
        assert "not a .py file" in caplog.text

    def test_load_all_idempotent(self):
        """Calling load_all twice loads each plugin once."""
        registry = PluginRegistry()
        first = registry.load_all()
        assert registry.load_all() == first
        assert len(registry.get_all()) == first
        assert len(registry.origins) == first


class TestPluginShadowing:
    """Test that later discovery sources shadow earlier ones with a warning."""

    def test_path_shadows_builtin(self, tmp_path, caplog):
        """A path plugin named 'spectrum' replaces the built-in with a warning."""
        (tmp_path / "spectrum_plugin.py").write_text(
            _plugin_source("ExtSpectrum", "spectrum", "Ext Spectrum")
        )
        registry = PluginRegistry(plugin_paths=[str(tmp_path)])
        registry.load_all()
        spectrum_cls = registry.get("spectrum")
        assert spectrum_cls is not None
        assert spectrum_cls.__name__ == "ExtSpectrum"
        assert registry.get_origin("spectrum") == ORIGIN_PATH
        assert "shadows" in caplog.text

    def test_entrypoint_shadows_builtin(self, tmp_path, monkeypatch, caplog):
        """An entry-point plugin named 'spectrum' replaces the built-in."""
        module_file = tmp_path / "ep_shadow_mod.py"
        module_file.write_text(_plugin_source("EpSpectrum", "spectrum", "EP Spectrum"))
        monkeypatch.setattr(sys, "path", [str(tmp_path)] + list(sys.path))
        eps = [types.SimpleNamespace(name="ep-spectrum", value="ep_shadow_mod:EpSpectrum")]
        with patch("importlib.metadata.entry_points", return_value=eps):
            registry = PluginRegistry()
            registry.load_all()
        spectrum_cls = registry.get("spectrum")
        assert spectrum_cls is not None
        assert spectrum_cls.__name__ == "EpSpectrum"
        assert registry.get_origin("spectrum") == ORIGIN_ENTRYPOINT
        assert "shadows" in caplog.text


class TestEntryPointDiscovery:
    """Test discovery of plugins via the 'audio-visualizer.plugins' group."""

    @staticmethod
    def _fake_eps(*values):
        return [
            types.SimpleNamespace(name=f"ep-{i}", value=value) for i, value in enumerate(values)
        ]

    def test_entry_point_module_attr(self, tmp_path, monkeypatch):
        """An entry point 'module:Class' loads that class."""
        module_file = tmp_path / "ep_mod_attr.py"
        module_file.write_text(_plugin_source("EntryPlugin", "entry", "Entry Plugin"))
        monkeypatch.setattr(sys, "path", [str(tmp_path)] + list(sys.path))
        with patch(
            "importlib.metadata.entry_points",
            return_value=self._fake_eps("ep_mod_attr:EntryPlugin"),
        ):
            registry = PluginRegistry()
            registry.load_all()
        assert registry.get("entry") is not None
        assert registry.get_origin("entry") == ORIGIN_ENTRYPOINT

    def test_entry_point_bare_module(self, tmp_path, monkeypatch):
        """An entry point with a bare module name loads every plugin class in it."""
        module_file = tmp_path / "ep_bare_mod.py"
        module_file.write_text(_plugin_source("BarePlugin", "bare", "Bare Plugin"))
        monkeypatch.setattr(sys, "path", [str(tmp_path)] + list(sys.path))
        with patch(
            "importlib.metadata.entry_points",
            return_value=self._fake_eps("ep_bare_mod"),
        ):
            registry = PluginRegistry()
            registry.load_all()
        assert registry.get("bare") is not None
        assert registry.get_origin("bare") == ORIGIN_ENTRYPOINT

    def test_entry_point_invalid_class_isolated(self, tmp_path, monkeypatch, caplog):
        """A broken entry-point class is skipped without breaking other loads."""
        module_file = tmp_path / "ep_bad_mod.py"
        module_file.write_text(
            "from audio_visualizer.visualizers.base import VisualizerPlugin\n"
            "\n"
            "\n"
            "class NotAPlugin(VisualizerPlugin):\n"
            "    pass\n"
        )
        monkeypatch.setattr(sys, "path", [str(tmp_path)] + list(sys.path))
        with patch(
            "importlib.metadata.entry_points",
            return_value=self._fake_eps("ep_bad_mod:NotAPlugin"),
        ):
            registry = PluginRegistry()
            registry.load_all()
        # No entry-point plugin made it in, built-ins are intact
        assert not [o for o in registry.origins.values() if o == ORIGIN_ENTRYPOINT]
        assert registry.get_origin("spectrum") == ORIGIN_BUILTIN
        assert "NotAPlugin" in caplog.text
        assert "Skipping." in caplog.text

    def test_entry_point_import_error_isolated(self, caplog):
        """An entry point pointing at a missing module is skipped with a warning."""
        with patch(
            "importlib.metadata.entry_points",
            return_value=self._fake_eps("definitely_missing_module_xyz:Nope"),
        ):
            registry = PluginRegistry()
            registry.load_all()
        assert "Failed to load plugin from entry point" in caplog.text
        assert "No module named" in caplog.text
        assert registry.get("spectrum") is not None

    def test_entry_points_scan_failure(self, caplog):
        """If the entry-point scan itself fails, built-ins still load."""
        with patch("importlib.metadata.entry_points", side_effect=ImportError("boom")):
            registry = PluginRegistry()
            registry.load_all()
        assert "Failed to scan entry points" in caplog.text
        assert registry.get("spectrum") is not None


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

    def test_load_user_plugin_syntax_error(self, tmp_path, caplog):
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
        assert "Failed to load user plugin 'bad_plugin'" in caplog.text
        assert "invalid syntax" in caplog.text
        assert "skipped" in caplog.text.lower()

    def test_load_user_plugin_missing_base_class(self, tmp_path, caplog):
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
        # No warning expected since there's no error, just no valid plugin
        assert "Warning" not in caplog.text

    def test_load_user_plugin_import_error(self, tmp_path, caplog):
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

        assert "Failed to load user plugin 'import_error_plugin'" in caplog.text
        assert "No module named" in caplog.text

    def test_load_user_plugin_invalid_metadata(self, tmp_path, caplog):
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

        assert "Failed to load user plugin 'bad_metadata_plugin'" in caplog.text

    def test_install_from_file_nonexistent_source(self, tmp_path, caplog):
        """Test that installing from a nonexistent file returns False."""
        user_dir = str(tmp_path / "plugins")
        os.makedirs(user_dir, exist_ok=True)

        registry = PluginRegistry(user_plugin_dir=user_dir)
        result = registry.install_from_file("/nonexistent/path/plugin.py")
        assert result is False
        assert "Error installing plugin to" in caplog.text


class TestRequiresCoreVersion:
    """v2.2.0 sec.6.2: PluginMetadata.requires_core_version gating."""

    def test_meets_core_version_basic(self):
        from audio_visualizer.visualizers.registry import _meets_core_version

        assert _meets_core_version("0.1") is True
        assert _meets_core_version("99.0") is False

    def test_meets_core_version_partial_spec(self):
        from audio_visualizer.visualizers.registry import _meets_core_version

        # '2' means >= 2.0; '99' means >= 99.0
        assert _meets_core_version("2") is True
        assert _meets_core_version("99") is False

    def test_meets_core_version_bad_input_is_satisfied(self):
        from audio_visualizer.visualizers.registry import _meets_core_version

        assert _meets_core_version("garbage") is True
        assert _meets_core_version("") is True

    def _register_fake(self, name, requires):
        from audio_visualizer.visualizers.base import (
            PluginMetadata,
            VisualizerPlugin,
        )
        from audio_visualizer.visualizers.registry import PluginRegistry

        class _P(VisualizerPlugin):
            metadata = PluginMetadata(
                name=name,
                display_name=name,
                description="core-version test plugin",
                requires_core_version=requires,
            )

            def build_filter(
                self,
                width,
                height,
                fps,
                options,
                audio_index=0,
                **kwargs,
            ):
                return f"[{audio_index}:a] testcore[size={width}x{height}][viz]"

        reg = PluginRegistry()
        reg._register(_P, "path")
        return reg

    def test_plugin_requiring_newer_core_is_skipped(self, caplog):

        reg = self._register_fake("needs-future", "99.0")
        assert "needs-future" not in reg.get_all()
        assert "Skipping plugin 'needs-future'" in caplog.text

    def test_plugin_with_satisfied_requirement_loads(self):
        reg = self._register_fake("old-friend", "0.1")
        assert "old-friend" in reg.get_all()

    def test_list_plugins_carries_requirement(self):
        reg = self._register_fake("old-friend", "2.0")
        entry = [p for p in reg.list_plugins() if p["name"] == "old-friend"][0]
        assert entry["requires_core_version"] == "2.0"


class TestTrustWarning:
    """v2.2.0 sec.6.4: one-line warning for untrusted plugin origins."""

    def test_path_origin_warns(self, caplog):
        import audio_visualizer.visualizers.registry as reg

        reg._warned_untrusted = False
        reg.warn_untrusted_plugins({"myplug": reg.ORIGIN_PATH, "spectrum": reg.ORIGIN_BUILTIN})
        assert "untrusted" in caplog.text
        assert "myplug" in caplog.text
        assert "spectrum" not in caplog.text.split("plugin(s)")[0]

    def test_entrypoint_origin_warns(self, caplog):
        import audio_visualizer.visualizers.registry as reg

        reg._warned_untrusted = False
        reg.warn_untrusted_plugins({"epplug": reg.ORIGIN_ENTRYPOINT})
        assert "epplug" in caplog.text

    def test_builtin_only_is_silent(self, caplog):
        import audio_visualizer.visualizers.registry as reg

        reg.warn_untrusted_plugins({"a": reg.ORIGIN_BUILTIN, "b": reg.ORIGIN_INSTALLED})
        assert "untrusted" not in caplog.text

    def test_warns_once_per_process(self, caplog):
        import audio_visualizer.visualizers.registry as reg

        reg._warned_untrusted = False
        reg.warn_untrusted_plugins({"x": reg.ORIGIN_PATH})
        first = caplog.text.count("untrusted")
        reg.warn_untrusted_plugins({"y": reg.ORIGIN_PATH})
        assert caplog.text.count("untrusted") == first
        reg._warned_untrusted = False
