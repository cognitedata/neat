from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from cognite.neat._data_model.models.dms import RequestSchema

T_Export = TypeVar("T_Export")


class DMSExporter(ABC, Generic[T_Export]):
    """This is the base class for all DMS exporters."""

    NEW_LINE = "\n"
    ENCODING = "utf-8"

    @abstractmethod
    def export(self, data_model: RequestSchema) -> T_Export:
        raise NotImplementedError()


class DMSFileExporter(DMSExporter[T_Export], ABC):
    @abstractmethod
    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        raise NotImplementedError()
