from dataclasses import dataclass

from cognite.neat.core._issues._base import NeatError


@dataclass(unsafe_hash=True)
class PluginError(NeatError):
    """No plugin of type '{type_}' registered under name '{name}'"""

    name: str
    type_: str


@dataclass(unsafe_hash=True)
class PluginLoadingError(PluginError):
    """Unable to load plugin of type '{type_}' registered under name '{name}' due to: {exception}"""

    exception: str


@dataclass(unsafe_hash=True)
class PluginDuplicateError(PluginError):
    """Plugin of type '{type_}' registered for under name '{name}' already exists"""

    pass
