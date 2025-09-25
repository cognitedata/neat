"""Plugin manager for external plugins."""

from importlib import metadata
from typing import Any, ClassVar

from ._base import NeatPlugin
from ._data_model import DataModelImporterPlugin, DataModelTransformerPlugin
from ._issues import PluginDuplicateError, PluginError, PluginLoadingError


class Plugin:
    """Plugin class for registering plugins registered via entry points (i.e. external plugins).

    Args:
        name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
        type_ (type): The type of the plugin.
        entry_point (EntryPoint): The entry point for the plugin.

    !!! note "name uniqueness"
        The name of the plugin must be lower case and unique across all plugins of the same kind.
        If two plugins have the same name, the exception will be raised.
    """

    def __init__(self, name: str, type_: type[NeatPlugin], entry_point: metadata.EntryPoint):
        self.name = name
        self.type_ = type_
        self.entry_point = entry_point

    def load(self) -> type[NeatPlugin]:
        try:
            return self.entry_point.load()
        except Exception as e:
            raise PluginLoadingError(self.name, self.type_.__name__, str(e)) from e


class PluginManager:
    """Plugin manager for external plugins."""

    _plugins_entry_points: ClassVar[dict[str, type[NeatPlugin]]] = {
        "cognite.neat.v0.plugins.data_model.importers": DataModelImporterPlugin,
        "cognite.neat.v0.plugins.data_model.transformers": DataModelTransformerPlugin,
    }

    def __init__(self, plugins: dict[tuple[str, type[NeatPlugin]], Any]) -> None:
        self._plugins = plugins

    def get(self, name: str, type_: type[NeatPlugin]) -> type[NeatPlugin]:
        """
        Returns desired plugin

        Args:
            name (str): The name of format (e.g. Excel) or action (e.g. merge) plugin is handling.
            type_ (type): The type of the plugin.
        """
        try:
            plugin_class = self._plugins[(name, type_)]
            return plugin_class
        except KeyError:
            raise PluginError(plugin_name=name, plugin_type=type_.__name__) from None

    @classmethod
    def load_plugins(cls, entry_points: metadata.EntryPoints | None = None) -> "PluginManager":
        """Load plugins from entry points and register them to the manager.
        This method scans the provided entry points for plugins defined in the
        `_plugins_entry_points` dictionary and registers them.

        Args:
            entry_points: Entry points to load plugins from. If None, uses the default entry points.
        """
        _plugins: dict[tuple[str, type[NeatPlugin]], Any] = {}

        entry_points = entry_points or metadata.entry_points()
        if hasattr(entry_points, "select"):
            for group, type_ in cls._plugins_entry_points.items():
                for entry_point in entry_points.select(group=group):
                    # Check for duplicate plugins
                    if (entry_point.name, type_) in _plugins:
                        raise PluginDuplicateError(plugin_name=entry_point.name, plugin_type=type_.__name__)

                    # Register the plugin
                    _plugins[(entry_point.name, type_)] = Plugin(entry_point.name, type_, entry_point).load()

        return cls(_plugins)


_manager_instance: PluginManager | None = None


def get_plugin_manager(force_reload: bool = False) -> PluginManager:
    """Get or create a singleton PluginManager instance."""
    global _manager_instance
    if force_reload or _manager_instance is None:
        _manager_instance = PluginManager.load_plugins()
    return _manager_instance
