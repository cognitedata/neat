from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import EntryPoint, entry_points
from typing import (
    Any,
    Generic,
    TypeVar,
    overload,
)

from cognite.neat.core._issues._base import NeatError
from cognite.neat.core.plugins.conceptual_data_model.extractors._base import (
    ConceptualDataModelExtractor,
)

__all__ = [
    "PKGPlugin",
    "Plugin",
    "PluginException",
    "PluginT",
    "get",
    "plugins",
    "register",
]


neat_entry_points = {
    "cognite.neat.core.plugins.conceptual_data_model.extractors": ConceptualDataModelExtractor,
}

_plugins: dict[tuple[str, type[Any]], Plugin] = {}


class PluginException(NeatError):
    pass


#: A generic type variable for plugins
PluginT = TypeVar("PluginT")


class Plugin(Generic[PluginT]):
    def __init__(self, name: str, kind: type[PluginT], module_path: str, class_name: str):
        self.name = name
        self.kind = kind
        self.module_path = module_path
        self.class_name = class_name
        self._class: type[PluginT] | None = None

    def get_class(self) -> type[PluginT]:
        if self._class is None:
            module = __import__(self.module_path, globals(), locals(), [""])
            self._class = getattr(module, self.class_name)
        return self._class


class PKGPlugin(Plugin[PluginT]):
    def __init__(self, name: str, kind: type[PluginT], entry_point: EntryPoint):
        self.name = name
        self.kind = kind
        self.entry_point = entry_point
        self._class: type[PluginT] | None = None

    def get_class(self) -> type[PluginT]:
        if self._class is None:
            self._class = self.entry_point.load()
        return self._class


def register(name: str, kind: type[Any], module_path, class_name):
    """
    Register the plugin for (name, kind). The module_path and
    class_name should be the path to a plugin class.
    """
    p = Plugin(name, kind, module_path, class_name)
    _plugins[(name, kind)] = p


def get(name: str, kind: type[PluginT]) -> type[PluginT]:
    """
    Return the class for the specified (name, kind). Raises a
    PluginException if unable to do so.
    """
    try:
        p: Plugin[PluginT] = _plugins[(name, kind)]
    except KeyError:
        raise PluginException("No plugin registered for (%s, %s)" % (name, kind))
    return p.get_class()


all_entry_points = entry_points()
if hasattr(all_entry_points, "select"):
    for entry_point, kind in neat_entry_points.items():
        for ep in all_entry_points.select(group=entry_point):
            _plugins[(ep.name, kind)] = PKGPlugin(ep.name, kind, ep)


@overload
def plugins(name: str | None = ..., kind: type[PluginT] = ...) -> Iterator[Plugin[PluginT]]: ...


@overload
def plugins(name: str | None = ..., kind: None = ...) -> Iterator[Plugin]: ...


def plugins(name: str | None = None, kind: type[PluginT] | None = None) -> Iterator[Plugin[PluginT]]:
    """
    A generator of the plugins.

    Pass in name and kind to filter... else leave None to match all.
    """
    for p in _plugins.values():
        if (name is None or name == p.name) and (kind is None or kind == p.kind):
            yield p


register(
    "excel",
    ConceptualDataModelExtractor,
    "cognite.neat.core.plugins.conceptual_data_model.extractors.excel",
    "ExcelExtractor",
)


def data_model_extract(source, level, format, *args, **kwargs):
    if level.lower() == "conceptual":
        return get(format, ConceptualDataModelExtractor)().extract(source=source, **kwargs)
