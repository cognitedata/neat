import warnings
from typing import Any

from cognite.neat.core import _plugin
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._utils.reader._base import NeatReader
from cognite.neat.core.plugins.data_model.importers._base import (
    DataModelImporter,
)
from cognite.neat.session._experimental import ExperimentalFlags

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class PluginAPI:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

        self.data_model = DataModelPlugins(self._state, self._verbose)


@session_class_wrapper
class DataModelPlugins:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def read(self, format: str, io: Any, **kwargs: Any) -> IssueList:
        """Provides access to the data model plugins."""
        warnings.filterwarnings("default")
        ExperimentalFlags.plugin.warn()

        reader = NeatReader.create(io)
        path = reader.materialize_path()

        self._state._raise_exception_if_condition_not_met(
            "Data Model Read",
            empty_data_model_store_required=True,
        )

        plugin = _plugin.get(format, DataModelImporter)
        cls = plugin.get_class()

        if isinstance(plugin, _plugin.ExternalPlugin):
            print(
                f"You are using an external plugin {cls.__name__}, which is not developed by the NEAT team."
                "\nUse it at your own risk."
            )

        importer = cls().configure(source=path, **kwargs)
        return self._state.rule_import(importer)
