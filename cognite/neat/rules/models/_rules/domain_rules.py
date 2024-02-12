from typing import ClassVar

from pydantic import Field

from .base import BaseMetadata, RoleTypes, RuleModel


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: str | list[str]


class DomainRules(RuleModel):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: dict = Field(alias="Properties")
    classes: dict | None = Field(None, alias="Classes")
