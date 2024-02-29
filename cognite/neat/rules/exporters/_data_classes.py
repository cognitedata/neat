from abc import ABC
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass
class UploadResultCore(ABC):
    name: str

    def __lt__(self, other: object) -> bool:
        if isinstance(other, UploadResult):
            return self.name < other.name
        else:
            return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UploadResult):
            return self.name == other.name
        else:
            return NotImplemented


@dataclass
class UploadResult(UploadResultCore):
    created: int = 0
    deleted: int = 0
    changed: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.created + self.deleted + self.changed + self.unchanged
