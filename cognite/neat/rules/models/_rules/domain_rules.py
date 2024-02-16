from typing import ClassVar

from pydantic import Field

from ._types import Class_, ParentClass_, Property_, StrOrList, ValueType_
from .base import (
    BaseMetadata,
    RoleTypes,
    RuleModel,
    SheetEntity,
    SheetList,
)


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: StrOrList


class DomainProperty(SheetEntity):
    class_: Class_ = Field(alias="Class")
    property_: Property_ = Field(alias="Property")
    value_type: ValueType_ = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)


class DomainClass(SheetEntity):
    class_: Class_ = Field(alias="Class")
    description: str | None = Field(None, alias="Description")
    parent: ParentClass_ = Field(alias="Parent Class")


class DomainRules(RuleModel):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")
