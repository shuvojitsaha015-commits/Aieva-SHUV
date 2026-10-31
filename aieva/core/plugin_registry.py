"""Automatic discovery and lookup of subject plugins.

The registry scans ``aieva/plugins/*/plugin.py`` with :mod:`importlib` and
:mod:`inspect` and registers every concrete :class:`SubjectPlugin` subclass it
finds. Adding a subject therefore never requires a change in the core.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from aieva.core.errors import PluginError
from aieva.core.plugin_base import PluginMeta, SubjectPlugin

DEFAULT_PACKAGE = "aieva.plugins"


class PluginRegistry:
    """Holds the available subject plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, SubjectPlugin] = {}

    # ------------------------------------------------------------------ API
    def register(self, plugin: SubjectPlugin) -> None:
        """Register (or replace) a plugin instance."""
        if not isinstance(plugin, SubjectPlugin):
            raise PluginError(f"{plugin!r} is not a SubjectPlugin")
        if not plugin.name:
            raise PluginError(f"{type(plugin).__name__} does not define a name")
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> SubjectPlugin:
        """Return the plugin registered under ``name``."""
        try:
            return self._plugins[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._plugins)) or "(none)"
            raise PluginError(f"Unknown plugin {name!r}. Available: {known}") from exc

    def names(self) -> list[str]:
        """The names of every registered plugin."""
        return sorted(self._plugins)

    def all(self) -> list[SubjectPlugin]:
        """Every registered plugin instance."""
        return [self._plugins[name] for name in self.names()]

    def subjects(self) -> list[PluginMeta]:
        """The metadata of every registered plugin, in display order."""
        metas = [plugin.meta() for plugin in self.all()]
        return sorted(metas, key=lambda meta: (meta.order, meta.name))

    def available_subjects(self) -> list[PluginMeta]:
        """Only the plugins whose optional dependencies are installed."""
        return [meta for meta in self.subjects() if meta.available]

    def clear(self) -> None:
        """Forget every registered plugin (used by tests)."""
        self._plugins.clear()

    # ------------------------------------------------------------ discovery
    def discover(
        self,
        package: str = DEFAULT_PACKAGE,
        package_path: Sequence[str] | Path | None = None,
    ) -> list[str]:
        """Import every ``<plugin>/plugin.py`` below ``package`` and register it.

        ``package_path`` allows the caller to point at a directory that is not
        importable as a package (used by the tests and by tooling).
        """
        if package_path is None:
            try:
                module = importlib.import_module(package)
            except ImportError as exc:  # pragma: no cover - defensive
                raise PluginError(f"Cannot import plugin package {package!r}: {exc}") from exc
            paths: Iterable[str] = list(getattr(module, "__path__", []))
        else:
            paths = [str(package_path)]

        discovered: list[str] = []
        for path in paths:
            base = Path(path)
            if not base.is_dir():
                continue
            for entry in sorted(base.iterdir()):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue
                module = self._import_plugin_module(package, entry)
                if module is None:
                    continue
                for plugin_class in self._plugin_classes(module):
                    try:
                        plugin = plugin_class()
                    except Exception as exc:  # noqa: BLE001 - a broken plugin must not kill the app
                        raise PluginError(
                            f"Could not instantiate plugin {plugin_class.__name__}: {exc}"
                        ) from exc
                    self.register(plugin)
                    discovered.append(plugin.name)
        return sorted(set(discovered))

    # ------------------------------------------------------------- internals
    @staticmethod
    def _import_plugin_module(package: str, directory: Path):
        """Import ``<package>.<dir>.plugin`` (or load it from the file)."""
        module_name = f"{package}.{directory.name}.plugin"
        try:
            return importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - fall back to a direct file load
            plugin_file = directory / "plugin.py"
            if not plugin_file.is_file():
                return None
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:  # noqa: BLE001 - a broken plugin is simply skipped
                sys.modules.pop(module_name, None)
                return None
            return module

    @staticmethod
    def _plugin_classes(module) -> list[type[SubjectPlugin]]:
        """Every concrete :class:`SubjectPlugin` subclass defined in ``module``."""
        classes: list[type[SubjectPlugin]] = []
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, SubjectPlugin) or obj is SubjectPlugin:
                continue
            if inspect.isabstract(obj):
                continue
            if obj.__module__ != module.__name__:
                continue
            classes.append(obj)
        return classes


#: The process wide registry.
REGISTRY = PluginRegistry()


def get_plugin(name: str = "math") -> SubjectPlugin:
    """Return the plugin ``name`` from the global registry (discovering on demand)."""
    if not REGISTRY.names():
        REGISTRY.discover()
    return REGISTRY.get(name)


def available_plugins() -> list[str]:
    """Names of every available plugin."""
    if not REGISTRY.names():
        REGISTRY.discover()
    return REGISTRY.names()


def subject_metas(only_available: bool = True) -> list[PluginMeta]:
    """The metadata of every subject (used to build the UI)."""
    if not REGISTRY.names():
        REGISTRY.discover()
    if only_available:
        return REGISTRY.available_subjects()
    return REGISTRY.subjects()


__all__ = [
    "DEFAULT_PACKAGE",
    "REGISTRY",
    "PluginMeta",
    "PluginRegistry",
    "available_plugins",
    "get_plugin",
    "subject_metas",
]
