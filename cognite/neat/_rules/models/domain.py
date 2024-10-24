import math
from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import Field, field_serializer, field_validator

from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ClassEntity, ClassEntityList

from ._base_input import InputComponent, InputRules
from ._base_rules import (
    BaseMetadata,
    BaseRules,
    RoleTypes,
    SheetList,
    SheetRow,
)
from ._types import ClassEntityType, InformationPropertyType, StrOrListType


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: StrOrListType

    def as_identifier(self) -> str:
        return "DomainRules"

    def get_prefix(self) -> str:
        return "domain"


class DomainProperty(SheetRow):
    class_: ClassEntityType = Field(alias="Class")
    property_: InformationPropertyType = Field(alias="Property")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    value_type: DataType | ClassEntity = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.class_, self.property_

    @field_serializer("max_count", when_used="json-unless-none")
    def serialize_max_count(self, value: int | float | None) -> int | float | None | str:
        if isinstance(value, float) and math.isinf(value):
            return None
        return value

    @field_validator("max_count", mode="before")
    def parse_max_count(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return float("inf")
        return value


class DomainClass(SheetRow):
    class_: ClassEntityType = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(None, alias="Description")
    parent: ClassEntityList | None = Field(alias="Parent Class")

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.class_,)

    @field_serializer("parent", when_used="unless-none")
    def serialize_parent(self, value: list[ClassEntity]) -> str:
        return ",".join([str(entry) for entry in value])


class DomainRules(BaseRules):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")
    last: "DomainRules | None" = Field(None, alias="Last")
    reference: "DomainRules | None" = Field(None, alias="Reference")


@dataclass
class DomainInputMetadata(InputComponent[DomainMetadata]):
    creator: str

    @classmethod
    def _get_verified_cls(cls) -> type[DomainMetadata]:
        return DomainMetadata


@dataclass
class DomainInputProperty(InputComponent[DomainProperty]):
    class_: str
    property_: str
    value_type: str
    name: str | None = None
    description: str | None = None
    min_count: int | None = None
    max_count: int | float | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DomainProperty]:
        return DomainProperty


@dataclass
class DomainInputClass(InputComponent[DomainClass]):
    class_: str
    name: str | None = None
    description: str | None = None
    parent: list[str] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DomainClass]:
        return DomainClass


@dataclass
class DomainInputRules(InputRules[DomainRules]):
    metadata: DomainInputMetadata
    properties: list[DomainInputProperty] = field(default_factory=list)
    classes: list[DomainInputClass] = field(default_factory=list)
    last: "DomainInputRules | None" = None
    reference: "DomainInputRules | None" = None

    @classmethod
    def _get_verified_cls(cls) -> type[DomainRules]:
        return DomainRules
