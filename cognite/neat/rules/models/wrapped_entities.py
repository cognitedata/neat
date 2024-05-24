import json
import re
from abc import ABC, abstractmethod
from collections.abc import Collection
from functools import total_ordering
from typing import Any, ClassVar, TypeVar

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, NodeId
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

        # raw filter case:
        if cls.__name__ == "RawFilter":
            if match := re.search(r"rawFilter\(([\s\S]*?)\)", data):
                return {"filter": match.group(1), "inner": None}
            else:
                raise ValueError(f"Cannot parse {cls.name} from {data}. Ill formatted raw filter.")

        # nodeType and hasData case:
        elif inner := data[len(cls.name) :].removeprefix("(").removesuffix(")"):
            return {"inner": [cls._inner_cls.load(entry.strip()) for entry in inner.split(",")]}
        else:
            raise ValueError(f"Cannot parse {cls.name} from {data}")

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

    @classmethod
    def from_dms_filter(cls, filter: dm.Filter) -> "DMSFilter":
        dumped = filter.dump()
        if (body := dumped.get(dm.filters.Equals._filter_name)) and (value := body.get("value")):
            space = value.get("space")
            external_id = value.get("externalId")
            if space is not None and external_id is not None:
                return NodeTypeFilter(inner=[DMSNodeEntity(space=space, externalId=external_id)])
        elif (body := dumped.get(dm.filters.In._filter_name)) and (values := body.get("values")):
            return NodeTypeFilter(
                inner=[
                    DMSNodeEntity(space=entry["space"], externalId=entry["externalId"])
                    for entry in values
                    if isinstance(entry, dict) and "space" in entry and "externalId" in entry
                ]
            )
        elif body := dumped.get(dm.filters.HasData._filter_name):
            return HasDataFilter(
                inner=[
                    ContainerEntity(space=entry["space"], externalId=entry["externalId"])
                    for entry in body
                    if isinstance(entry, dict) and "space" in entry and "externalId" in entry
                ]
            )

        raise ValueError(f"Cannot convert {filter._filter_name} to {cls.__name__}")


class NodeTypeFilter(DMSFilter):
    name: ClassVar[str] = "nodeType"
    _inner_cls: ClassVar[type[DMSNodeEntity]] = DMSNodeEntity
    inner: list[DMSNodeEntity] | None = None  # type: ignore[assignment]

    @property
    def nodes(self) -> list[NodeId]:
        return [node.as_id() for node in self.inner or []]

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


class RawFilter(DMSFilter):
    name: ClassVar[str] = "rawFilter"
    filter: str
    inner: None = None  # type: ignore[assignment]

    def as_dms_filter(self) -> dm.Filter:  # type: ignore[override]
        try:
            return dm.Filter.load(json.loads(self.filter))
        except json.JSONDecodeError as e:
            raise ValueError(f"Error loading raw filter: {e}") from e

    @property
    def is_empty(self) -> bool:
        return self.filter is None

    def __repr__(self) -> str:
        return self.filter
