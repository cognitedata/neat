"""Plugin manager for external plugins."""

from importlib.metadata import EntryPoint, entry_points
from typing import (
    Any,
    Generic,
    TypeVar,
)

from ._issues import PluginClassLoadError, PluginError
from .data_model.importers import (
    DataModelImporter,
)

# Here we configure entry points for external plugins to be registered
# in the plugin manager.
plugins_entry_points = {
    "cognite.neat.plugins.data_model.importers": DataModelImporter,
}


#: A generic type variable for plugins
T_Plugin = TypeVar("T_Plugin")


class ExternalPlugin(Generic[T_Plugin]):
    """Plugin class for plugins registered via entry points (external).

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        kind (type[T_Plugin]): The type of the plugin.
        entry_point (EntryPoint): The entry point for the plugin.


    !!! note "name uniqueness"
        The name of the plugin must be lower case and unique across all plugins of the same kind.
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
            try:
                self._class = self.entry_point.load()
            except Exception as e:
                raise PluginClassLoadError(self.name, self.kind.__name__, str(e)) from e
        return self._class


_plugins: dict[tuple[str, type[Any]], ExternalPlugin] = {}


def get(name: str, kind: type[T_Plugin]) -> ExternalPlugin[T_Plugin]:
    """
    Returns desired plugin

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        kind (type[T_Plugin]): The type of the plugin.
    """
    try:
        p: ExternalPlugin = _plugins[(name, kind)]
    except KeyError:
        raise PluginError(name=name, kind=kind.__name__) from None
    return p


# This will register all the external plugins
all_entry_points = entry_points()
if hasattr(all_entry_points, "select"):
    for entry_point, kind in plugins_entry_points.items():
        for ep in all_entry_points.select(group=entry_point):
            _plugins[(ep.name, kind)] = ExternalPlugin(ep.name, kind, ep)
