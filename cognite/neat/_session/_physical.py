from typing import Any

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer.deployer import DeploymentOptions, SchemaDeployer
from cognite.neat._data_model.exporters import DMSAPIExporter, DMSExcelExporter, DMSYamlExporter
from cognite.neat._data_model.importers import DMSAPIImporter, DMSTableImporter
from cognite.neat._data_model.models.dms import DataModelReference
from cognite.neat._data_model.validation.dms import DmsDataModelValidation
from cognite.neat._state_machine import PhysicalState
from cognite.neat._store._store import NeatStore
from cognite.neat._utils._reader import NeatReader

from ._wrappers import session_wrapper


class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient) -> None:
        self._store = store
        self._client = client
        self.read = ReadPhysicalDataModel(self._store, self._client)
        self.write = WritePhysicalDataModel(self._store, self._client)

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

    def yaml(self, io: Any) -> None:
        """Read physical data model from YAML file"""

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_yaml(path)
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

    def __init__(self, store: NeatStore, client: NeatClient) -> None:
        self._store = store
        self._client = client

    def yaml(self, io: Any) -> None:
        """Write physical data model to YAML file"""

        file_path = NeatReader.create(io).materialize_path()
        writer = DMSYamlExporter()

        return self._store.write_physical(writer, file_path=file_path)

    def excel(self, io: Any) -> None:
        """Write physical data model to Excel file"""

        file_path = NeatReader.create(io).materialize_path()
        writer = DMSExcelExporter()

        return self._store.write_physical(writer, file_path=file_path)

    def cdf(self, dry_run: bool = True, rollback: bool = True) -> None:
        """Write physical data model to CDF

        Args:
            dry_run (bool): If true, the changes will not be applied to CDF.
            rollback (bool): If true, all changes will be rolled back if any error occurs.

        """
        writer = DMSAPIExporter()
        on_success = SchemaDeployer(self._client, DeploymentOptions(dry_run=dry_run, auto_rollback=rollback))
        return self._store.write_physical(writer, on_success)
