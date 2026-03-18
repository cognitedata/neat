"""Plugin manager for external plugins."""

import warnings
from importlib import metadata
from typing import Any, ClassVar, TypeVar, overload

from ._interfaces import NeatPlugin, PhysicalDataModelReaderPlugin

T_ClassInstance = TypeVar("T_ClassInstance")


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

    def load(self) -> type[NeatPlugin] | None:
        try:
            return self.entry_point.load()
        except Exception as e:
            warnings.warn(
                f"Skipping plugin '{self.name}' of type '{self.type_.__name__}' due to: {e}",
                UserWarning,
                stacklevel=2,
            )
            return None


class PluginManager:
    """Plugin manager for external plugins."""

    _plugins_entry_points: ClassVar[dict[str, type[NeatPlugin]]] = {
        PhysicalDataModelReaderPlugin._entry_point: PhysicalDataModelReaderPlugin,
    }

    def __init__(self, plugins: dict[tuple[str, type[NeatPlugin]], type[NeatPlugin]]) -> None:
        self._plugins = plugins

    @overload
    def get(self, type_: type[NeatPlugin]) -> dict[str, type[NeatPlugin]]: ...

    @overload
    def get(self, type_: type[NeatPlugin], name: str) -> type[NeatPlugin] | None: ...

    def get(
        self, type_: type[NeatPlugin], name: str | None = None
    ) -> type[NeatPlugin] | dict[str, type[NeatPlugin]] | None:
        """
        Returns desired plugin(s).

        Args:
            type_ (type): The type of the plugin.
            name (str, optional): The name of the plugin. If provided, returns a single plugin.
                                  If not provided, returns all plugins of the given type.

        Returns:
            type[NeatPlugin] | dict[str,type[NeatPlugin]]: Single plugin if name is provided,
                                                       list of plugins if name is None.
        """

        return (
            {
                plugin_name: plugin
                for (plugin_name, plugin_type), plugin in self._plugins.items()
                if plugin_type == type_
            }
            if name is None
            else self._plugins.get((name, type_), None)
        )

    @classmethod
    def load_plugins(cls, entry_points: metadata.EntryPoints | None = None) -> "PluginManager":
        """Load plugins from entry points and register them to the manager.
        This method scans the provided entry points for plugins defined in the
        `_plugins_entry_points` dictionary and registers them.

        Args:
            entry_points: Entry points to load plugins from. If None, uses the default entry points.
        """
        plugins: dict[tuple[str, type[NeatPlugin]], Any] = {}

        entry_points = entry_points or metadata.entry_points()
        if hasattr(entry_points, "select"):
            for group, type_ in cls._plugins_entry_points.items():
                for entry_point in entry_points.select(group=group):
                    # Check for duplicate plugins
                    if (entry_point.name, type_) in plugins:
                        warnings.warn(
                            (
                                f"Plugin '{entry_point.name}' of type '{type_.__name__}' "
                                "is already loaded. Skipping duplicate."
                            ),
                            UserWarning,
                            stacklevel=2,
                        )
                        continue

                    # Register the plugin
                    if plugin := Plugin(entry_point.name, type_, entry_point).load():
                        plugins[(entry_point.name, type_)] = plugin

        return cls(plugins)


_manager: PluginManager | None = None


def get_plugin_manager(force_reload: bool = False) -> PluginManager:
    """Get or create a singleton PluginManager instance."""
    global _manager
    if force_reload or _manager is None:
        _manager = PluginManager.load_plugins()
    return _manager
