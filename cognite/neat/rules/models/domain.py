import math
from typing import Any, ClassVar

from pydantic import Field, field_serializer, field_validator, model_serializer
from pydantic_core.core_schema import SerializationInfo

from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import ClassEntity, ParentEntityList

from ._base import (
    BaseMetadata,
    BaseRules,
    RoleTypes,
    SheetEntity,
    SheetList,
)
from ._types import PropertyType, StrOrListType


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: StrOrListType

    def as_identifier(self) -> str:
        return "DomainRules"


class DomainProperty(SheetEntity):
    class_: ClassEntity = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    value_type: DataType | ClassEntity = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)

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


class DomainClass(SheetEntity):
    class_: ClassEntity = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(None, alias="Description")
    parent: ParentEntityList | None = Field(alias="Parent Class")


class DomainRules(BaseRules):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")
    last: "DomainRules | None" = Field(None, alias="Last")
    reference: "DomainRules | None" = Field(None, alias="Reference")

    @model_serializer(mode="plain", when_used="always")
    def domain_rules_serializer(self, info: SerializationInfo) -> dict[str, Any]:
        kwargs = vars(info)
        output: dict[str, Any] = {
            "Metadata" if info.by_alias else "metadata": self.metadata.model_dump(**kwargs),
            "Properties" if info.by_alias else "properties": [prop.model_dump(**kwargs) for prop in self.properties],
        }
        if self.classes or not info.exclude_none:
            output["Classes" if info.by_alias else "classes"] = [
                cls.model_dump(**kwargs) for cls in self.classes or []
            ] or None
        return output
