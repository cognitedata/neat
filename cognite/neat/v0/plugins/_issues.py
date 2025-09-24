from dataclasses import dataclass

from cognite.neat.v0.core._issues.errors import _NEAT_ERRORS_BY_NAME, NeatError


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


# Register the errors in the _NEAT_ERRORS_BY_NAME dictionary
_NEAT_ERRORS_BY_NAME.update(
    {
        "PluginError": PluginError,
        "PluginLoadingError": PluginLoadingError,
        "PluginDuplicateError": PluginDuplicateError,
    }
)
