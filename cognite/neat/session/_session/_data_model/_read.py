from typing import Any, Literal
from zipfile import Path

from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.importers._base import BaseImporter
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._issues.warnings._general import MissingCogniteClientWarning
from cognite.neat.core._utils.reader._base import NeatReader
from cognite.neat.plugins._manager import get_plugin_manager
from cognite.neat.plugins.data_model.importers._base import DataModelImporterPlugin
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import NeatSessionError, session_class_wrapper

InternalReaderName = Literal["excel", "ontology", "yaml"]


@session_class_wrapper
class ReadAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self, name: str, io: str | Path, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """

        # Clean the input name once before matching.
        clean_name: InternalReaderName | str = name.strip().lower()

        # The match statement cleanly handles each case.
        match clean_name:
            case "excel":
                return self.excel(io, **kwargs)

            case "ontology":
                return self.ontology(io)

            case "yaml":
                return self.yaml(io, **kwargs)

            case _:  # The wildcard '_' acts as the default 'else' case.
                return self._plugin(name, io, **kwargs)

    def _plugin(self, name: str, io: str | Path, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """

        # Some plugins may not support the io argument
        reader = NeatReader.create(io)
        path = reader.materialize_path()

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

    def excel(self, io: str | Path, *, enable_manual_edit: bool = False) -> IssueList:
        """Reads a Neat Excel Data Model to the data model store.
        The data model spreadsheets may contain conceptual or physical data model definitions.

            Args:
                io: file path to the Excel sheet
                enable_manual_edit: If True, the user will be able to re-import data model
                    which where edit outside of NeatSession
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        self._state._raise_exception_if_condition_not_met(
            "Read Excel Data Model",
            empty_data_model_store_required=not enable_manual_edit,
        )

        return self._state.data_model_import(importers.ExcelImporter(path), enable_manual_edit)

    def ontology(self, io: str | Path) -> IssueList:
        """Reads an OWL ontology source into NeatSession.

        Args:
            io: file path or url to the OWL file
        """

        self._state._raise_exception_if_condition_not_met(
            "Read Ontology",
            empty_data_model_store_required=True,
        )

        reader = NeatReader.create(io)
        importer = importers.OWLImporter.from_file(reader.materialize_path(), source_name=f"file {reader!s}")
        return self._state.data_model_import(importer)

    def yaml(self, io: str | Path, *, format: Literal["neat", "toolkit"] = "neat") -> IssueList:
        """Reads a yaml with either neat data mode, or several toolkit yaml files to
        import Data Model(s) into NeatSession.

        Args:
            io: File path to the Yaml file in the case of "neat" yaml, or path to a zip folder or directory with several
                Yaml files in the case of "toolkit".
            format: The format of the yaml file(s). Can be either "neat" or "toolkit".

        Example:
            ```python
            neat.read.yaml("path_to_toolkit_yamls")
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Read YAML data model",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        importer: BaseImporter
        if format == "neat":
            importer = importers.DictImporter.from_yaml_file(path, source_name=f"{reader!s}")
        elif format == "toolkit":
            dms_importer = importers.DMSImporter.from_path(path, self._state.client)
            if dms_importer.issue_list.has_warning_type(MissingCogniteClientWarning):
                raise NeatSessionError(
                    "No client provided. You are referencing Cognite containers in your data model, "
                    "NEAT needs a client to lookup the container definitions. "
                    "Please set the client in the session, NeatSession(client=client)."
                )
            importer = dms_importer
        else:
            raise NeatValueError(f"Unsupported YAML format: {format}")
        return self._state.data_model_import(importer)
