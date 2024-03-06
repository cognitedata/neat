from typing import ClassVar

from pydantic import Field

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
