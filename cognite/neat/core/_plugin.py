"""Module for plugin management in NEAT."""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import EntryPoint, entry_points
from typing import (
    Any,
    Generic,
    TypeVar,
    overload,
)

from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.physical._unverified import (
    UnverifiedPhysicalDataModel,
)
from cognite.neat.core._issues._base import NeatError
from cognite.neat.core._plugins.data_model.importers import (
    DataModelImporterPlugin,
)

__all__ = [
    "NeatPlugin",
    "Plugin",
    "PluginException",
    "T_Plugin",
    "get",
    "plugins",
    "register",
]


neat_entry_points = {
    "cognite.neat.core._plugins.data_model.importers": DataModelImporterPlugin,
}

_plugins: dict[tuple[str, type[Any]], Plugin] = {}


class PluginException(NeatError):
    pass


#: A generic type variable for plugins
T_Plugin = TypeVar("T_Plugin")


class Plugin(Generic[T_Plugin]):
    def __init__(self, name: str, kind: type[T_Plugin], module_path: str, class_name: str):
        self.name = name
        self.kind = kind
        self.module_path = module_path
        self.class_name = class_name
        self._class: type[T_Plugin] | None = None

    def get_class(self) -> type[T_Plugin]:
        if self._class is None:
            print(self.module_path)
            module = __import__(self.module_path, globals(), locals(), [""])
            self._class = getattr(module, self.class_name)
        return self._class


class NeatPlugin(Plugin[T_Plugin]):
    """Neat plugin class for plugins registered via entry points.

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        kind (type[T_Plugin]): The type of the plugin.
        entry_point (EntryPoint): The entry point for the plugin.


    !!! note "name uniqueness"
        The name of the plugin must be unique across all plugins of the same kind.
        If two plugins have the same name, the first one registered will be used.
        This is to avoid conflicts and ensure that the correct plugin is used.
    """

    def __init__(self, name: str, kind: type[T_Plugin], entry_point: EntryPoint):
        self.name = name
        self.kind = kind
        self.entry_point = entry_point
        self._class: type[T_Plugin] | None = None

    def get_class(self) -> type[T_Plugin]:
        if self._class is None:
            self._class = self.entry_point.load()
        return self._class


def register(name: str, kind: type[Any], module_path: str, class_name: str) -> None:
    """
    Register a plugin to the plugin manager.

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        kind (type[Any]): The type of the plugin.
        module_path (str): The path to the module containing the plugin class.
        class_name (str): The name of the plugin class.

    """
    p = Plugin(name, kind, module_path, class_name)
    _plugins[(name, kind)] = p


def get(name: str, kind: type[T_Plugin]) -> type[T_Plugin]:
    """
    Returns desired plugin

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        kind (type[T_Plugin]): The type of the plugin.
    """
    try:
        p: Plugin[T_Plugin] = _plugins[(name, kind)]
    except KeyError:
        raise PluginException(f"No plugin registered for ({name}, {kind})") from None
    return p.get_class()


@overload
def plugins(name: str | None = ..., kind: type[T_Plugin] = ...) -> Iterator[Plugin[T_Plugin]]: ...


@overload
def plugins(name: str | None = ..., kind: None = ...) -> Iterator[Plugin]: ...


def plugins(name: str | None = None, kind: type[T_Plugin] | None = None) -> Iterator[Plugin[T_Plugin]]:
    """
    A generator of the plugins.

    Pass in name and kind to filter... else leave None to match all.
    """
    for p in _plugins.values():
        if (name is None or name == p.name) and (kind is None or kind == p.kind):
            yield p


# This will register all the external plugins
all_entry_points = entry_points()
if hasattr(all_entry_points, "select"):
    for entry_point, kind in neat_entry_points.items():
        for ep in all_entry_points.select(group=entry_point):
            _plugins[(ep.name, kind)] = NeatPlugin(ep.name, kind, ep)


register(
    "excel",
    DataModelImporterPlugin,
    "cognite.neat.core._plugins.data_model.importers._excel",
    "ExcelDataModelImporterPlugin",
)


def data_model_import(
    source: Any, format: str, *args: Any, **kwargs: Any
) -> UnverifiedPhysicalDataModel | UnverifiedConceptualDataModel:
    return get(format, DataModelImporterPlugin)().configure(source=source, **kwargs)  # type: ignore
