"""
Plugin Registry

Handles automatic discovery, loading, and management of visualizer plugins.
Plugins are discovered from the visualizers/ directory by importing each .py file.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

from audio_visualizer.logging_config import logger

from .base import PluginMetadata, PluginOption, VisualizerPlugin


class PluginRegistry:
    """
    Central registry for visualizer plugins.

    Automatically discovers plugins from the visualizers/ directory
    and provides methods to list, load, and access them.

    Usage:
        registry = PluginRegistry()
        registry.load_all()  # Auto-discover plugins

        # List all available plugins
        for plugin_cls in registry.get_all():
            meta = plugin_cls.get_metadata()
            logger.info(f"{meta.name}: {meta.display_name}")

        # Get a specific plugin by name
        spectrum_plugin = registry.get("spectrum")
    """

    def __init__(self, user_plugin_dir: str | None = None):
        self._plugins: dict[str, type[VisualizerPlugin]] = {}
        self._user_plugin_dir = user_plugin_dir

    def load_all(self) -> int:
        """
        Auto-discover and load all plugins.

        Loads built-in plugins from this package, then loads user plugins
        from the user_plugin_dir if specified.

        Returns:
            Number of plugins loaded
        """
        # Load built-in plugins from this package
        self._load_from_package()

        # Load user plugins from custom directory if specified
        if self._user_plugin_dir and os.path.isdir(self._user_plugin_dir):
            self._load_from_directory(self._user_plugin_dir)

        return len(self._plugins)

    def _validate_plugin(self, plugin_cls: type) -> bool:
        """Validate a plugin class has required attributes and valid schemas.

        Returns True if valid, False otherwise.
        """
        # Check metadata exists
        try:
            meta = plugin_cls.get_metadata()
        except NotImplementedError:
            logger.warning(
                f"Plugin '{plugin_cls.__name__}': missing 'metadata' attribute. Skipping."
            )
            return False

        # Check metadata has required fields
        if not meta.name:
            logger.warning(
                f"Plugin '{plugin_cls.__name__}': metadata 'name' is empty. Skipping."
            )
            return False

        # Check options is a list of PluginOption instances
        if not isinstance(plugin_cls.options, list):
            logger.warning(
                f"Plugin '{plugin_cls.__name__}': 'options' must be a list. Skipping."
            )
            return False

        for opt in plugin_cls.options:
            if not isinstance(opt, PluginOption):
                logger.warning(
                    f"Plugin '{plugin_cls.__name__}': options must contain PluginOption instances. Skipping."
                )
                return False
            # Validate option has required fields
            if not opt.name or not opt.type or opt.default is None:
                logger.warning(
                    f"Plugin '{plugin_cls.__name__}': option '{opt.name}' has invalid schema. Skipping."
                )
                return False

        # Check build_filter is implemented (not the abstract base method)
        if "build_filter" not in plugin_cls.__dict__:
            logger.warning(
                f"Plugin '{plugin_cls.__name__}': missing 'build_filter' method. Skipping."
            )
            return False

        return True

    def get_all_with_errors(self) -> tuple[dict, list]:
        """Return all plugins and any that failed validation.

        Returns:
            Tuple of (plugins_dict, error_list) where plugins_dict contains
            successfully loaded plugins and error_list contains dicts with
            plugin name and error message for failed plugins.
        """
        plugins = dict(self._plugins)
        errors = []

        # Check for user plugins that may have failed validation
        if self._user_plugin_dir and os.path.isdir(self._user_plugin_dir):
            for py_file in sorted(Path(self._user_plugin_dir).glob("*.py")):
                if py_file.name.startswith("_") or py_file.name == "__init__.py":
                    continue
                plugin_name = py_file.stem
                if plugin_name not in plugins:
                    # Try to load and validate to get the actual error
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            f"temp.{plugin_name}", py_file
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if (
                                    isinstance(attr, type)
                                    and issubclass(attr, VisualizerPlugin)
                                    and attr is not VisualizerPlugin
                                ):
                                    # Validate and get the actual error
                                    if not hasattr(attr, 'options') or not isinstance(attr.options, list):
                                        errors.append({
                                            "name": plugin_name,
                                            "error": "Missing or invalid 'options' attribute",
                                        })
                                    elif not attr.metadata or not attr.metadata.name:
                                        errors.append({
                                            "name": plugin_name,
                                            "error": "Missing plugin name in metadata",
                                        })
                                    else:
                                        errors.append({
                                            "name": plugin_name,
                                            "error": "Plugin failed validation during load",
                                        })
                                    break
                    except Exception:
                        errors.append({
                            "name": plugin_name,
                            "error": "Plugin failed validation during load",
                        })

        return plugins, errors

    def _load_from_package(self):
        """Load built-in plugins from this package."""
        importlib.invalidate_caches()

        # Get all modules in this package
        package_dir = Path(__file__).parent
        for py_file in sorted(package_dir.glob("*.py")):
            if py_file.name in ("__init__.py", "base.py", "registry.py"):
                continue
            if py_file.name.startswith("_"):
                continue

            module_name = f"audio_visualizer.visualizers.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                # Find all VisualizerPlugin subclasses in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, VisualizerPlugin)
                        and attr is not VisualizerPlugin
                    ):
                        # Validate plugin before loading
                        if self._validate_plugin(attr):
                            meta = attr.get_metadata()
                            self._plugins[meta.name] = attr
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load built-in plugin '{py_file.stem}' ({py_file}): {e}"
                ) from e

    def _load_from_directory(self, directory: str):
        """Load plugins from a custom user directory."""
        importlib.invalidate_caches()

        for py_file in sorted(Path(directory).glob("*.py")):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue

            module_name = f"user_plugins.{py_file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, VisualizerPlugin)
                            and attr is not VisualizerPlugin
                        ):
                            # Validate plugin before loading
                            if self._validate_plugin(attr):
                                meta = attr.get_metadata()
                                self._plugins[meta.name] = attr
                            else:
                                logger.warning(
                                    f"  Plugin '{py_file.stem}' failed validation. Skipping."
                                )
            except Exception as e:
                logger.warning(f"Failed to load user plugin '{py_file.stem}' from {py_file}")
                logger.warning(f"  Error: {e}")
                logger.warning(
                    "  The plugin was skipped. Fix the error or remove the file to resolve."
                )

    def get_all(self) -> dict[str, type[VisualizerPlugin]]:
        """Return all loaded plugins as {name: class} dict."""
        return dict(self._plugins)

    def get(self, name: str) -> type[VisualizerPlugin] | None:
        """Get a plugin class by its unique name."""
        return self._plugins.get(name)

    def get_metadata(self, name: str) -> PluginMetadata | None:
        """Get metadata for a plugin by name."""
        plugin_cls = self._plugins.get(name)
        if plugin_cls:
            return plugin_cls.get_metadata()
        return None

    def list_plugins(self) -> list[dict]:
        """Return a list of all plugins with their metadata."""
        result = []
        for name, plugin_cls in sorted(self._plugins.items()):
            meta = plugin_cls.get_metadata()
            result.append(
                {
                    "name": meta.name,
                    "display_name": meta.display_name,
                    "description": meta.description,
                    "author": meta.author,
                    "version": meta.version,
                    "icon": meta.icon,
                }
            )
        return result

    @property
    def _user_dir(self) -> str:
        """Get the user plugin directory, creating it if needed."""
        if self._user_plugin_dir is None:
            # Default to ~/.audio_visualizer/plugins
            home = Path.home()
            default_dir = str(home / ".audio_visualizer" / "plugins")
            os.makedirs(default_dir, exist_ok=True)
            return default_dir
        return self._user_plugin_dir

    def install_from_file(self, filepath: str) -> bool:
        """
        Install a plugin from a Python file.

        The file must contain a class that inherits from VisualizerPlugin
        and defines the required metadata and build_filter method.

        Returns True if successfully installed, False otherwise.
        """
        import shutil

        user_dir = self._user_dir
        dest = Path(user_dir) / os.path.basename(filepath)
        try:
            shutil.copy2(filepath, dest)
            return True
        except Exception as e:
            logger.error(f"Error installing plugin to {dest}: {e}")
            return False

    def uninstall(self, name: str) -> bool:
        """Uninstall a user-installed plugin by name."""
        user_dir = self._user_dir
        for py_file in Path(user_dir).glob("*.py"):
            # Check if this file contains the plugin
            try:
                spec = importlib.util.spec_from_file_location(f"temp.{py_file.stem}", py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"temp.{py_file.stem}"] = module
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, VisualizerPlugin)
                            and attr is not VisualizerPlugin
                        ):
                            meta = attr.get_metadata()
                            if meta.name == name:
                                py_file.unlink()
                                return True
            except Exception:
                continue
        return False
