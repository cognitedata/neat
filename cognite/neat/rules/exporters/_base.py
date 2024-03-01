from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    @abstractmethod
    def export(self) -> T_Export:
        raise NotImplementedError

    @abstractmethod
    def export_to_file(self, filepath: Path) -> None:
        raise NotImplementedError
