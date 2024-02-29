from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from ._data_classes import UploadResult

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    @abstractmethod
    def export_to_file(self, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self) -> T_Export:
        raise NotImplementedError

    @abstractmethod
    def export_to_cdf(self, client, dry_run: bool = False) -> list[UploadResult]:
        raise NotImplementedError
