from abc import ABC
from typing import Any, ClassVar

from pydantic import BaseModel, model_serializer, model_validator

from cognite.neat.rules.models.entities import ContainerEntity, DMSNodeEntity, Entity


class WrappedEntity(BaseModel, ABC):
    name: ClassVar[str]
    _inner_cls: ClassVar[type[Entity]]
    inner: Entity | list[Entity] | None

    @classmethod
    def load(cls): ...

    @model_validator(mode="before")
    def _load(cls, data: Any) -> dict:
        if isinstance(data, dict):
            return data
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")
        result = cls._parse(data)
        return result

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self):
        return self.id

    @property
    def id(self) -> str:
        return f"{self.name}({','.join([str(entity) for entity in self.entities])})"


class NodeTypeFilter(WrappedEntity):
    name: ClassVar[str] = "nodeType"
    _inner_cls: ClassVar[type[DMSNodeEntity]] = DMSNodeEntity
    inner: DMSNodeEntity | None = None


class HasDataFilter(WrappedEntity):
    name: ClassVar[str] = "hasData"
    _inner_cls: ClassVar[type[ContainerEntity]] = ContainerEntity
    inner: list[ContainerEntity] | None = None
