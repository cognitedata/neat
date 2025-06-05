"""Plugin manager for external plugins."""

from importlib import metadata
from typing import (
    Any,
    ClassVar,
    Generic,
    TypeAlias,
    TypeVar,
)

from ._issues import PluginDuplicateError, PluginError, PluginLoadingError
from .data_model.importers import (
    DataModelImporterPlugin,
)

# Here we configure entry points where external plugins are going to be registered.
plugins_entry_points = {
    "cognite.neat.plugins.data_model.importers": DataModelImporterPlugin,
}


#: A generic type variable for plugins

NeatPlugin: TypeAlias = DataModelImporterPlugin


T_Plugin = TypeVar("T_Plugin", bound=NeatPlugin)


class Plugin(Generic[T_Plugin]):
    """Plugin class for registering plugins registered via entry points (i.e. external plugins).

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        type_ (type[T_Plugin]): The type of the plugin.
        entry_point (EntryPoint): The entry point for the plugin.


    !!! note "name uniqueness"
        The name of the plugin must be lower case and unique across all plugins of the same kind.
        If two plugins have the same name, the exception will be raised .

    """

    def __init__(self, name: str, type_: type[T_Plugin], entry_point: metadata.EntryPoint):
        self.name = name
        self.type_ = type_
        self.entry_point = entry_point

    def load(self) -> type[T_Plugin]:
        try:
            return self.entry_point.load()
        except Exception as e:
            raise PluginLoadingError(self.name, self.type_.__name__, str(e)) from e


class PluginManager:
    """Plugin manager for external plugins."""

    _plugins_entry_points: ClassVar[dict[str, Any]] = {
        "cognite.neat.plugins.data_model.importers": DataModelImporterPlugin,
    }

    def __init__(self, plugins: dict[tuple[str, type[Any]], T_Plugin]) -> None:
        self._plugins = plugins

    def get(self, name: str, type_: type[T_Plugin]) -> NeatPlugin:
        """
        Returns desired plugin

        Args:
            name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
            type_ (type[T_Plugin]): The type of the plugin.
        """
        try:
            return self._plugins[(name, type_)]
        except KeyError:
            raise PluginError(name=name, type_=type_.__name__) from None

    @classmethod
    def load_plugins(cls, entry_points: metadata.EntryPoints | None = None) -> "PluginManager":
        """Load plugins from entry points and register them to the manager.
        This method scans the provided entry points for plugins defined in the
        `_plugins_entry_points` dictionary and registers them.

        Args:
            entry_points: Entry points to load plugins from. If None, uses the default entry points.
        """

        _plugins: dict[tuple[str, type[Any]], Any] = {}

        print(cls._plugins_entry_points)

        entry_points = entry_points or metadata.entry_points()
        if hasattr(entry_points, "select"):
            for group, type_ in cls._plugins_entry_points.items():
                for entry_point in entry_points.select(group=group):
                    # Check for duplicate plugins
                    if (entry_point.name, type_) in _plugins:
                        raise PluginDuplicateError(name=entry_point.name, type_=type_.__name__)

                    # Register the plugin
                    _plugins[(entry_point.name, type_)] = Plugin(entry_point.name, type_, entry_point).load()

        return cls(_plugins)


manager = PluginManager.load_plugins()
