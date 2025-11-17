from typing import Any, Literal

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer.deployer import DeploymentOptions, SchemaDeployer
from cognite.neat._data_model.exporters import (
    DMSAPIExporter,
    DMSAPIJSONExporter,
    DMSAPIYAMLExporter,
    DMSExcelExporter,
    DMSExporter,
    DMSTableJSONExporter,
    DMSTableYamlExporter,
)
from cognite.neat._data_model.exporters._table_exporter.workbook import WorkbookOptions
from cognite.neat._data_model.importers import DMSAPIImporter, DMSImporter, DMSTableImporter
from cognite.neat._data_model.models.dms import DataModelReference
from cognite.neat._data_model.validation.dms import DmsDataModelValidation
from cognite.neat._exceptions import UserInputError
from cognite.neat._state_machine import PhysicalState
from cognite.neat._store._store import NeatStore
from cognite.neat._utils._reader import NeatReader
from cognite.neat._utils.useful_types import ModusOperandi

from ._wrappers import session_wrapper


class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient, mode: ModusOperandi) -> None:
        self._store = store
        self._client = client
        self.read = ReadPhysicalDataModel(self._store, self._client)
        self.write = WritePhysicalDataModel(self._store, self._client, mode)

    def _repr_html_(self) -> str:
        if not isinstance(self._store.state, PhysicalState):
            return "No physical data model. Get started by reading physical data model <em>.physica_data_mode.read</em>"

        dm = self._store.physical_data_model[-1]

        html = ["<div>"]
        html.append(
            f"<h3>Data Model: {dm.data_model.space}:{dm.data_model.external_id}(version={dm.data_model.version})</h3>"
        )
        html.append("<table style='border-collapse: collapse;'>")
        html.append("<tr><th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Component</th>")
        html.append("<th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Count</th></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Views</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.views)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Containers</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.containers)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Spaces</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.spaces)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Node Types</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.node_types)}</td></tr>")

        html.append("</table>")
        html.append("</div>")

        return "".join(html)


@session_wrapper
class ReadPhysicalDataModel:
    """Read physical data model from various sources into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient) -> None:
        self._store = store
        self._client = client

    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Read physical data model from YAML file(s)

        Args:
            io (Any): The file or directory path or buffer to read from.
            format (Literal["neat", "toolkit"]): The format of the input file(s).
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        path = NeatReader.create(io).materialize_path()

        reader: DMSImporter
        if format == "neat":
            reader = DMSTableImporter.from_yaml(path)
        elif format == "toolkit":
            reader = DMSAPIImporter.from_yaml(path)
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")
        on_success = DmsDataModelValidation(self._client)

        return self._store.read_physical(reader, on_success)

    def json(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Read physical data model from JSON file(s)

        Args:
            io (Any): The file or directory path or buffer to read from.
            format (Literal["neat", "toolkit"]): The format of the input file(s).
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        path = NeatReader.create(io).materialize_path()

        reader: DMSImporter
        if format == "neat":
            reader = DMSTableImporter.from_json(path)
        elif format == "toolkit":
            reader = DMSAPIImporter.from_json(path)
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")
        on_success = DmsDataModelValidation(self._client)

        return self._store.read_physical(reader, on_success)

    def excel(self, io: Any) -> None:
        """Read physical data model from Excel file"""

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_excel(path)
        on_success = DmsDataModelValidation(self._client)

        return self._store.read_physical(reader, on_success)

    def cdf(self, space: str, external_id: str, version: str) -> None:
        """Read physical data model from CDF

        Args:
            space (str): The schema space of the data model.
            external_id (str): The external id of the data model.
            version (str): The version of the data model.

        """
        reader = DMSAPIImporter.from_cdf(
            DataModelReference(space=space, external_id=external_id, version=version), self._client
        )
        on_success = DmsDataModelValidation(self._client)

        return self._store.read_physical(reader, on_success)


@session_wrapper
class WritePhysicalDataModel:
    """Write physical data model to various sources from NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient, mode: ModusOperandi) -> None:
        self._store = store
        self._client = client
        self._mode = mode

    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Write physical data model to YAML file

        Args:
            io (Any): The file path or buffer to write to.
            format (Literal["neat", "toolkit"]): The format of the output file
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        file_path = NeatReader.create(io).materialize_path()
        writer: DMSExporter
        if format == "neat":
            writer = DMSTableYamlExporter()
        elif format == "toolkit":
            writer = DMSAPIYAMLExporter()
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        return self._store.write_physical(writer, file_path=file_path)

    def json(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Write physical data model to JSON file

        Args:
            io (Any): The file path or buffer to write to.
            format (Literal["neat", "toolkit"]): The format of the output file
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        file_path = NeatReader.create(io).materialize_path()
        writer: DMSExporter
        if format == "neat":
            writer = DMSTableJSONExporter()
        elif format == "toolkit":
            writer = DMSAPIJSONExporter()
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        return self._store.write_physical(writer, file_path=file_path)

    def excel(self, io: Any, skip_other_spaces: bool = True) -> None:
        """Write physical data model to Excel file

        Args:
            io (Any): The file path or buffer to write to.
            skip_other_spaces (bool): If true, only properties in the same space as the data model will be written.

        """

        file_path = NeatReader.create(io).materialize_path()
        options = WorkbookOptions(skip_properties_in_other_spaces=skip_other_spaces)
        writer = DMSExcelExporter(options=options)

        return self._store.write_physical(writer, file_path=file_path)

    def cdf(self, dry_run: bool = True, rollback: bool = True, drop_data: bool = False) -> None:
        """Write physical data model with views, containers, and spaces that are in the same space as the data model
        to CDF.

        This method depends on the session mode set when creating the NeatSession.
            - In 'additive' mode, only new or updates to data models/views/containers will be applied.
                You cannot remove views from data models, properties from views or containers, or
                indexes or constraints from containers.
            - In 'rebuild' mode, the data model in CDF will be made to exactly match the data model in Neat.
                If there are any breaking changes, Neat will delete and recreate the relevant
                data model/view/container. However, if drop_data is set to False, Neat will treat
                containers as 'additive' and will not delete any containers or remove properties,
                indexes, or constraints. To fully rebuild the data model, including containers, set drop_data to True.

        Args:
            dry_run (bool): If true, the changes will not be applied to CDF. Instead, Neat will
                report what changes would have been made.
            rollback (bool): If true, all changes will be rolled back if any error occurs.
            drop_data (bool): Only applicable if the session mode is 'rebuild'. If

        """
        writer = DMSAPIExporter()
        options = DeploymentOptions(
            dry_run=dry_run, auto_rollback=rollback, drop_data=drop_data, modus_operandi=self._mode
        )
        on_success = SchemaDeployer(self._client, options)
        return self._store.write_physical(writer, on_success)
