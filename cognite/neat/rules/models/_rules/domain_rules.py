from typing import ClassVar

from pydantic import Field

from .base import BaseMetadata, Entity, RoleTypes, RuleModel, SheetList


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: str | list[str]


class DomainProperty(Entity):
    class_: str = Field(alias="Class")
    property: str = Field(alias="Property")
    description: str | None = Field(None, alias="Description")
    value_type: str | None = Field(None, alias="Value Type")
    min_count: int | None = Field(None, alias="Min Count")
    max_count: int | float | None = Field(None, alias="Max Count")


class DomainClass(Entity):
    class_: str = Field(alias="Class")
    description: str | None = Field(None, alias="Description")
    parent: str | None = Field(None, alias="Parent Class")


class DomainRules(RuleModel):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")
