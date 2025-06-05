from dataclasses import dataclass

from cognite.neat.core._issues._base import NeatError


@dataclass(unsafe_hash=True)
class PluginError(NeatError):
    """No plugin of kind '{kind}' registered for format/action '{name}'"""

    name: str
    kind: str


@dataclass(unsafe_hash=True)
class PluginClassLoadError(PluginError):
    """Unable to load class for plugin of kind '{kind}' registered for format/action '{name}' due to: {exception}"""

    exception: str
