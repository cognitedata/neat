from abc import ABC, abstractmethod
from collections.abc import Collection
from functools import total_ordering
from typing import Any, ClassVar, TypeVar

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, NodeApply, NodeApplyList, NodeId
from pydantic import BaseModel, model_serializer, model_validator

from cognite.neat.rules.models.entities import ContainerEntity, DMSNodeEntity, Entity


@total_ordering
class WrappedEntity(BaseModel, ABC):
    name: ClassVar[str]
    _inner_cls: ClassVar[type[Entity]]
    inner: list[Entity] | None

    @classmethod
    def load(cls: "type[T_WrappedEntity]", data: Any) -> "T_WrappedEntity":
        if isinstance(data, cls):
            return data
        return cls.model_validate(data)

    @model_validator(mode="before")
    def _load(cls, data: Any) -> dict:
        if isinstance(data, dict):
            return data
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")
        elif not data.casefold().startswith(cls.name.casefold()):
            raise ValueError(f"Expected {cls.name} but got {data}")
        result = cls._parse(data)
        return result

    @classmethod
    def _parse(cls, data: str) -> dict:
        if data.casefold() == cls.name.casefold():
            return {"inner": None}
        inner = data[len(cls.name) :].removeprefix("(").removesuffix(")")
        return {"inner": [cls._inner_cls.load(entry.strip()) for entry in inner.split(",")]}

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self):
        return self.id

    @property
    def id(self) -> str:
        inner = self.as_tuple()[1:]
        return f"{self.name}({','.join(inner)})"

    @property
    def is_empty(self) -> bool:
        return self.inner is None or (isinstance(self.inner, list) and not self.inner)

    def dump(self) -> str:
        return str(self)

    def as_tuple(self) -> tuple[str, ...]:
        entities: list[str] = [str(inner) for inner in self.inner or []]
        return self.name, *entities

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, WrappedEntity):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WrappedEntity):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self) -> str:
        return self.id


T_WrappedEntity = TypeVar("T_WrappedEntity", bound=WrappedEntity)


class DMSFilter(WrappedEntity):
    @abstractmethod
    def as_dms_filter(self, default: Any | None = None) -> dm.filters.Filter:
        raise NotImplementedError


class NodeTypeFilter(DMSFilter):
    name: ClassVar[str] = "nodeType"
    _inner_cls: ClassVar[type[DMSNodeEntity]] = DMSNodeEntity
    inner: list[DMSNodeEntity] | None = None  # type: ignore[assignment]

    @property
    def nodes(self) -> NodeApplyList:
        return NodeApplyList([NodeApply(node.space, node.external_id) for node in self.inner or []])

    def as_dms_filter(self, default: Collection[NodeId] | None = None) -> dm.Filter:
        if self.inner is not None:
            node_ids = [node.as_id() for node in self.inner]
        elif default is not None:
            node_ids = list(default)
        else:
            raise ValueError("Empty nodeType filter, please provide a default node.")
        if len(node_ids) == 1:
            return dm.filters.Equals(
                ["node", "type"], {"space": node_ids[0].space, "externalId": node_ids[0].external_id}
            )
        else:
            return dm.filters.In(
                ["node", "type"],
                [
                    {"space": node.space, "externalId": node.external_id}
                    for node in sorted(node_ids, key=lambda node: node.as_tuple())
                ],
            )


class HasDataFilter(DMSFilter):
    name: ClassVar[str] = "hasData"
    _inner_cls: ClassVar[type[ContainerEntity]] = ContainerEntity
    inner: list[ContainerEntity] | None = None  # type: ignore[assignment]

    def as_dms_filter(self, default: Collection[ContainerId] | None = None) -> dm.Filter:
        containers: list[ContainerId]
        if self.inner:
            containers = [container.as_id() for container in self.inner]
        elif default:
            containers = list(default)
        else:
            raise ValueError("Empty hasData filter, please provide a default containers.")

        return dm.filters.HasData(
            # Sorting to ensure deterministic order
            containers=sorted(containers, key=lambda container: container.as_tuple())  # type: ignore[union-attr]
        )
