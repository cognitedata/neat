from typing import Any

from cognite.neat.core._data_model.importers._base import BaseImporter


class DataModelImporterPlugin:
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def configure(self, source: Any, *args: Any, **kwargs: Any) -> BaseImporter:
        """Return a configure plugin for data model import."""
        raise NotImplementedError()
