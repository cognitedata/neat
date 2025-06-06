from dataclasses import dataclass

from cognite.neat.core._issues._base import NeatError


@dataclass(unsafe_hash=True)
class PluginError(NeatError, ImportError):
    """No plugin of type '{plugin_type}' registered under name '{plugin_name}'"""

    plugin_name: str
    plugin_type: str


@dataclass(unsafe_hash=True)
class PluginLoadingError(PluginError):
    """Unable to load plugin of type '{plugin_type}' registered under name '{plugin_name}' due to: {exception}"""

    exception: str


@dataclass(unsafe_hash=True)
class PluginDuplicateError(PluginError):
    """Plugin of type '{plugin_type}' registered for under name '{plugin_name}' already exists"""

    ...
