from typing import Any

from cognite.neat._client import NeatClient
from cognite.neat._data_model.exporters import DMSExcelExporter, DMSYamlExporter
from cognite.neat._data_model.importers import DMSAPIImporter, DMSTableImporter
from cognite.neat._data_model.models.dms import DataModelReference
from cognite.neat._data_model.validation.dms import DmsDataModelValidation
from cognite.neat._store._store import NeatStore
from cognite.neat._utils._reader import NeatReader

from ._wrappers import session_wrapper


class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient) -> None:
        self._store = store
        self._client = client
        self.read = ReadPhysicalDataModel(self._store, self._client)
        self.write = WritePhysicalDataModel(self._store)


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

    def __init__(self, store: NeatStore) -> None:
        self._store = store

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
