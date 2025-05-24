from collections.abc import Hashable
from dataclasses import dataclass, field


@dataclass
class Property:
    location: str
    value_representation: str


@dataclass
class PropertyChange(Property):
    previous_representation: str


@dataclass
class ResourceDifference:
    resource_id: Hashable
    added: list[Property] = field(default_factory=list)
    removed: list[Property] = field(default_factory=list)
    changed: list[PropertyChange] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Check if there are any differences."""
        return bool(self.added or self.removed or self.changed)


@dataclass
class DeployResult:
    diffs: list[ResourceDifference] = field(default_factory=list)
