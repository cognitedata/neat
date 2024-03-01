from abc import ABC
from dataclasses import dataclass, field
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
    skipped: int = 0
    failed_created: int = 0
    failed_changed: int = 0
    error_messages: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.deleted + self.changed + self.unchanged

    @property
    def failed(self) -> int:
        return self.failed_created + self.failed_changed
