from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, TypeVar

from cognite.client import CogniteClient

from ._models import UploadResult

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    @abstractmethod
    def export_to_file(self, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self) -> T_Export:
        raise NotImplementedError


class CDFExporter(ABC, Generic[T_Export]):
    @abstractmethod
    def export_to_cdf(self, client: CogniteClient, dry_run: bool = False) -> Iterable[UploadResult]:
        raise NotImplementedError
