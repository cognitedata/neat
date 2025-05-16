from typing import Any

from cognite.neat.core._data_model.importers._base import BaseImporter


class DataModelImporter:
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def configure(self, source: Any, **kwargs: Any) -> BaseImporter:
        """Return a configure plugin for data model import."""
        raise NotImplementedError()
