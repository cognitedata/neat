

from typing import Any
from cognite.neat._store._store import NeatStore
from cognite.neat._utils.reader._base import NeatReader
from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.exporters import DMSTableExporter

class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store
        self.read = ReadPhysicalDataModel(self._store)
        self.write = WritePhysicalDataModel(self._store)
    
    def __call__(self):
        return self._store._physical[-1]

class ReadPhysicalDataModel:
    """Read physical data model from various sources into NeatSession graph store."""
    def __init__(self, store: NeatStore) -> None:
        self._store = store

    def yaml(self, io : Any) -> None:
        """Read physical data model from YAML file"""

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_yaml(path)

        return self._store.read_physical(reader)

class WritePhysicalDataModel:
    """Write physical data model to various sources from NeatSession graph store."""
    def __init__(self, store: NeatStore) -> None:
        self._store = store

    def yaml(self, io : Any, exclude_none: bool = False) -> None:
        """Write physical data model to YAML file"""

        file_path = NeatReader.create(io).materialize_path()
        writer = DMSTableExporter(exclude_none=exclude_none)

        return self._store.write_physical(writer, file_path=file_path)