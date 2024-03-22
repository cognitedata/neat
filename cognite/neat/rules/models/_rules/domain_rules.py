from typing import Any, ClassVar

from pydantic import Field, model_serializer
from pydantic_core.core_schema import SerializationInfo

from ._types import ParentClassType, PropertyType, SemanticValueType, StrOrListType
from .base import (
    BaseMetadata,
    RoleTypes,
    RuleModel,
    SheetEntity,
    SheetList,
)


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: StrOrListType


class DomainProperty(SheetEntity):
    property_: PropertyType = Field(alias="Property")
    value_type: SemanticValueType = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)


class DomainClass(SheetEntity):
    description: str | None = Field(None, alias="Description")
    parent: ParentClassType = Field(alias="Parent Class")


class DomainRules(RuleModel):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")

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
