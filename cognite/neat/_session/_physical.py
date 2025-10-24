from typing import Any

from cognite.neat._data_model.exporters import DMSExcelExporter, DMSYamlExporter
from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.models.dms._quality_assessment import DmsQualityAssessment
from cognite.neat._store._store import NeatStore
from cognite.neat._utils._reader import NeatReader

from ._wrappers import session_wrapper


class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store
        self.read = ReadPhysicalDataModel(self._store)
        self.write = WritePhysicalDataModel(self._store)


@session_wrapper
class ReadPhysicalDataModel:
    """Read physical data model from various sources into NeatSession graph store."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    def yaml(self, io: Any) -> None:
        """Read physical data model from YAML file"""

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_yaml(path)

        return self._store.read_physical(reader, DmsQualityAssessment)

    def excel(self, io: Any) -> None:
        """Read physical data model from Excel file"""

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_excel(path)

        return self._store.read_physical(reader, DmsQualityAssessment)


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
