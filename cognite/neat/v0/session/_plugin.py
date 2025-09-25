import warnings
from pathlib import Path
from typing import Any

from cognite.neat.v0.core._issues._base import IssueList
from cognite.neat.v0.core._utils.reader._base import NeatReader
from cognite.neat.v0.plugins import DataModelImporterPlugin, get_plugin_manager
from cognite.neat.v0.session._experimental import ExperimentalFlags

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class PluginAPI:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

        self.data_model = DataModelPlugins(self._state)


@session_class_wrapper
class DataModelPlugins:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    def read(self, name: str, io: str | Path | None = None, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.plugin.warn()

        # Some plugins may not support the io argument
        if io:
            reader = NeatReader.create(io)
            path = reader.materialize_path()
        else:
            path = None

        self._state._raise_exception_if_condition_not_met(
            "Data Model Read",
            empty_data_model_store_required=True,
        )

        plugin_manager = get_plugin_manager()
        plugin = plugin_manager.get(name, DataModelImporterPlugin)

        print(
            f"You are using an external plugin {plugin.__name__}, which is not developed by the NEAT team."
            "\nUse it at your own risk."
        )

        return self._state.data_model_import(plugin().configure(io=path, **kwargs))
