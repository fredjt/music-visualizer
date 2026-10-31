"""
Plugin Registry

Handles automatic discovery, loading, and management of visualizer plugins.

Discovery sources, in order (later sources shadow earlier ones, with a
warning): ``builtin`` (this package's visualizers/ directory),
``entrypoint`` (distributions registering the ``audio-visualizer.plugins``
entry-point group), ``installed`` (plugins installed via ``--install-plugin``,
in ~/.audio_visualizer/plugins or a custom user dir), and ``path`` (explicit
plugin files/dirs via ``--plugin-path`` or AUDIO_VISUALIZER_PLUGIN_PATH).
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from audio_visualizer.logging_config import logger

from .base import PluginMetadata, PluginOption, VisualizerPlugin

# Entry-point group that third-party distributions register plugins in.
ENTRY_POINT_GROUP = "audio-visualizer.plugins"
# Environment variable holding os.pathsep-separated external plugin paths.
PLUGIN_PATH_ENV = "AUDIO_VISUALIZER_PLUGIN_PATH"

# Plugin discovery origins
ORIGIN_BUILTIN = "builtin"
ORIGIN_ENTRYPOINT = "entrypoint"
ORIGIN_INSTALLED = "installed"
ORIGIN_PATH = "path"


def _core_version_tuple() -> tuple[int, ...] | None:
    """The installed core version as a numeric tuple, or None if unknown."""
    try:
        from importlib.metadata import version

        parts = version("musicvisualizer").split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except Exception:
        return None


_warned_untrusted = False


def warn_untrusted_plugins(origins: dict[str, str]) -> None:
    """One-line warning (once per process) for plugins from untrusted origins.

    v2.2.0 sec.6.4: plugins discovered via `path` (AUDIO_VISUALIZER_PLUGIN_PATH)
    or `entrypoint` (installed packages) are arbitrary Python code; the
    warning makes the trust decision explicit instead of silent.
    """
    global _warned_untrusted
    if _warned_untrusted:
        return
    names = sorted(n for n, o in origins.items() if o in (ORIGIN_PATH, ORIGIN_ENTRYPOINT))
    if not names:
        return
    _warned_untrusted = True
    logger.warning(
        f"Loading {len(names)} third-party plugin(s) from untrusted sources "
        f"({', '.join(names)}); plugins are arbitrary Python code - review "
        f"them before use (see the README security model)"
    )


def _meets_core_version(required: str) -> bool:
    """True when the installed core satisfies *required* (e.g. '2.2').

    Mirrors the ffmpeg version check: an unparseable requirement or an
    undetectable core version is treated as satisfied (the plugin still
    loads; a broken plugin fails later with its own error).
    """
    try:
        req = tuple(int(p) for p in str(required).split(".") if p.isdigit())
    except ValueError:
        return True
    core = _core_version_tuple()
    if core is None or not req:
        return True
    width = max(len(core), len(req))
    core = core + (0,) * (width - len(core))
    req = req + (0,) * (width - len(req))
    return core >= req


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

    def __init__(
        self,
        user_plugin_dir: str | None = None,
        plugin_paths: list[str] | None = None,
    ):
        self._plugins: dict[str, type[VisualizerPlugin]] = {}
        self._origins: dict[str, str] = {}
        self._user_plugin_dir = user_plugin_dir
        self._plugin_paths: list[str] = list(plugin_paths or [])
        self._loaded = False

    def load_all(self) -> int:
        """
        Auto-discover and load all plugins.

        Loads plugins from every discovery source in order: built-ins,
        entry points, installed plugins, and explicit plugin paths. Later
        sources shadow earlier ones (a warning is emitted when that happens).

        Returns:
            Number of plugins loaded
        """
        if self._loaded:
            return len(self._plugins)

        # Load built-in plugins from this package
        self._load_from_package()

        # Load plugins registered by installed distributions
        self._load_from_entry_points()

        # Load installed plugins and external plugin directories
        for directory, origin in self._discovery_dirs():
            self._load_from_directory(directory, origin)

        # Load explicit plugin files; _load_from_path warns about paths that
        # are neither existing files nor directories
        for path in self._plugin_paths:
            if not os.path.isdir(path):
                self._load_from_path(path)

        # v2.2.0 sec.6.4: make the trust decision explicit once per process
        warn_untrusted_plugins(self._origins)

        self._loaded = True
        return len(self._plugins)

    def _validate_plugin(self, plugin_cls: type[VisualizerPlugin]) -> bool:
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
            logger.warning(f"Plugin '{plugin_cls.__name__}': metadata 'name' is empty. Skipping.")
            return False

        # Check options is a list of PluginOption instances. (Runtime guards:
        # third-party classes may not honour the declared schema.)
        if not isinstance(plugin_cls.options, list):  # type: ignore[reportUnnecessaryIsInstance]
            logger.warning(f"Plugin '{plugin_cls.__name__}': 'options' must be a list. Skipping.")
            return False

        for opt in plugin_cls.options:
            if not isinstance(opt, PluginOption):  # type: ignore[reportUnnecessaryIsInstance]
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

    def _register(self, plugin_cls: type[VisualizerPlugin], origin: str) -> bool:
        """Register a validated plugin class under its metadata name.

        Discovery sources load in a fixed order, so a later source shadows
        an earlier one; a warning is emitted whenever that happens.

        Returns:
            True if the plugin was (re)registered, False if the same class
            was already registered under that name.
        """
        meta = plugin_cls.get_metadata()
        if meta.requires_core_version and not _meets_core_version(meta.requires_core_version):
            core = _core_version_tuple()
            logger.warning(
                f"Skipping plugin '{meta.name}': requires audio-visualizer "
                f">= {meta.requires_core_version} (installed: "
                f"{'.'.join(str(p) for p in core) if core else 'unknown'})"
            )
            return False
        existing = self._plugins.get(meta.name)
        if existing is plugin_cls:
            # Same class loaded twice (e.g. a re-scan of the same source)
            return False
        if existing is not None:
            logger.warning(
                f"Plugin '{meta.name}' from '{origin}' source shadows the "
                f"'{self._origins.get(meta.name, 'unknown')}' plugin; "
                f"the '{origin}' version will be used."
            )
        self._plugins[meta.name] = plugin_cls
        self._origins[meta.name] = origin
        return True

    def _discovery_dirs(self) -> list[tuple[str, str]]:
        """Return (directory, origin) pairs for file-based plugin discovery.

        Covers the installed-plugin directory and any directory passed via
        --plugin-path / AUDIO_VISUALIZER_PLUGIN_PATH.
        """
        dirs: list[tuple[str, str]] = []
        installed_dir = self._user_plugin_dir or str(Path.home() / ".audio_visualizer" / "plugins")
        if os.path.isdir(installed_dir):
            dirs.append((installed_dir, ORIGIN_INSTALLED))
        for path in self._plugin_paths:
            if os.path.isdir(path):
                dirs.append((path, ORIGIN_PATH))
        return dirs

    def get_all_with_errors(self) -> tuple[dict[str, type[VisualizerPlugin]], list[dict[str, str]]]:
        """Return all plugins and any that failed validation.

        Returns:
            Tuple of (plugins_dict, error_list) where plugins_dict contains
            successfully loaded plugins and error_list contains dicts with
            plugin name and error message for failed plugins.
        """
        plugins = dict(self._plugins)
        errors: list[dict[str, str]] = []

        # Check external plugin files that may have failed validation
        for directory, _origin in self._discovery_dirs():
            for py_file in sorted(Path(directory).glob("*.py")):
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
                                    opts_attr = getattr(attr, "options", None)
                                    if not isinstance(opts_attr, list):
                                        errors.append(
                                            {
                                                "name": plugin_name,
                                                "error": "Missing or invalid 'options' attribute",
                                            }
                                        )
                                    elif not attr.metadata or not attr.metadata.name:
                                        errors.append(
                                            {
                                                "name": plugin_name,
                                                "error": "Missing plugin name in metadata",
                                            }
                                        )
                                    else:
                                        errors.append(
                                            {
                                                "name": plugin_name,
                                                "error": "Plugin failed validation during load",
                                            }
                                        )
                                    break
                    except Exception:
                        errors.append(
                            {
                                "name": plugin_name,
                                "error": "Plugin failed validation during load",
                            }
                        )

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
                            self._register(attr, ORIGIN_BUILTIN)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load built-in plugin '{py_file.stem}' ({py_file}): {e}"
                ) from e

    def _load_from_entry_points(self) -> None:
        """Load plugins registered via the ``audio-visualizer.plugins`` group.

        Entry-point values may be ``module:ClassName`` or a bare module name
        (every VisualizerPlugin subclass in it is loaded). Failures are
        isolated: a broken entry point is skipped with a warning.
        """
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
        except Exception as e:
            logger.warning(f"Failed to scan entry points for plugins: {e}")
            return

        for ep in eps:
            try:
                module_name, _, attr_name = ep.value.partition(":")
                module = importlib.import_module(module_name)
                if attr_name:
                    cls = getattr(module, attr_name, None)
                    candidates = [cls] if isinstance(cls, type) else []
                else:
                    candidates = [
                        attr
                        for attr in vars(module).values()
                        if isinstance(attr, type)
                        and issubclass(attr, VisualizerPlugin)
                        and attr is not VisualizerPlugin
                    ]
                for cls in candidates:
                    if (
                        issubclass(cls, VisualizerPlugin)
                        and cls is not VisualizerPlugin
                        and self._validate_plugin(cls)
                    ):
                        self._register(cls, ORIGIN_ENTRYPOINT)
            except Exception as e:
                logger.warning(
                    f"Failed to load plugin from entry point '{ep.name}' ({ep.value}): {e}"
                )

    def _load_from_path(self, path: str) -> None:
        """Load plugin(s) from an explicit file or directory path."""
        if os.path.isfile(path):
            if not path.endswith(".py"):
                logger.warning(f"Plugin path '{path}' is not a .py file. Skipping.")
                return
            self._load_plugin_file(path, ORIGIN_PATH)
        elif os.path.isdir(path):
            self._load_from_directory(path, ORIGIN_PATH)
        else:
            logger.warning(f"Plugin path '{path}' does not exist. Skipping.")

    def _load_from_directory(self, directory: str, origin: str) -> None:
        """Load plugins from a directory of .py files."""
        importlib.invalidate_caches()

        for py_file in sorted(Path(directory).glob("*.py")):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue
            self._load_plugin_file(py_file, origin)

    def _load_plugin_file(self, py_file: str | Path, origin: str) -> None:
        """Import one plugin file and validate/register the classes in it.

        Failures are isolated: a broken plugin file is skipped with a warning
        instead of aborting the whole load.
        """
        py_file = Path(py_file)
        module_name = f"external_plugins.{py_file.stem}"
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
                            self._register(attr, origin)
                        else:
                            logger.warning(
                                f"  Plugin '{py_file.stem}' failed validation. Skipping."
                            )
        except Exception as e:
            logger.warning(f"Failed to load user plugin '{py_file.stem}' from {py_file}")
            logger.warning(f"  Error: {e}")
            logger.warning("  The plugin was skipped. Fix the error or remove the file to resolve.")

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

    def get_origin(self, name: str) -> str | None:
        """Return the discovery origin of a loaded plugin.

        One of 'builtin', 'entrypoint', 'installed', or 'path'; None if the
        plugin is not loaded.
        """
        return self._origins.get(name)

    @property
    def origins(self) -> dict[str, str]:
        """Return {name: origin} for all loaded plugins."""
        return dict(self._origins)

    def list_plugins(self, category: str | None = None) -> list[dict[str, Any]]:
        """Return a list of all plugins with their metadata.

        Args:
            category: If provided, only return plugins in this category.
        """
        result: list[dict[str, Any]] = []
        for _name, plugin_cls in sorted(self._plugins.items()):
            meta = plugin_cls.get_metadata()
            if category and meta.category != category:
                continue
            result.append(
                {
                    "name": meta.name,
                    "origin": self._origins.get(meta.name, ORIGIN_BUILTIN),
                    "display_name": meta.display_name,
                    "description": meta.description,
                    "author": meta.author,
                    "version": meta.version,
                    "icon": meta.icon,
                    "category": meta.category,
                    "requires_ffmpeg_version": meta.requires_ffmpeg_version,
                    "requires_core_version": meta.requires_core_version,
                    "input_types": meta.input_types,
                }
            )
        return result

    def get_categories(self) -> list[str]:
        """Return a sorted list of unique plugin categories."""
        return sorted({cls.get_metadata().category for cls in self._plugins.values()})

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
