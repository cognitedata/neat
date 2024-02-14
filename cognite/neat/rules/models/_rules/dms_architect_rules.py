from datetime import datetime
from typing import ClassVar

from pydantic import Field

from cognite.neat.rules.models._rules.information_rules import InformationMetadata
from cognite.neat.rules.models.value_types import ValueType

from .base import BaseRules, RoleTypes, SheetEntity, SheetList
from .domain_rules import DomainMetadata


class DMSArchitectMetadata(InformationMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms_architect
    space: str
    external_id: str = Field(alias="externalId")

    @classmethod
    def from_information_architect_metadata(
        cls, metadata: InformationMetadata, space: str | None = None, externalId: str | None = None
    ):
        metadata_as_dict = metadata.model_dump()
        metadata_as_dict["space"] = space or "neat-playground"
        metadata_as_dict["externalId"] = externalId or "neat_model"
        return cls(**metadata_as_dict)

    @classmethod
    def from_domain_expert_metadata(
        cls,
        metadata: DomainMetadata,
        space: str | None = None,
        externalId: str | None = None,
        version: str | None = None,
        contributor: str | list[str] | None = None,
        created: datetime | None = None,
        updated: datetime | None = None,
    ):
        information = InformationMetadata.from_domain_expert_metadata(
            metadata, None, None, version, contributor, created, updated
        ).model_dump()

        return cls.from_information_architect_metadata(information)


class DMSProperty(SheetEntity):
    class_: str = Field(alias="Class")
    property: str = Field(alias="Property")
    description: str | None = None
    value_type: ValueType = Field(alias="Value Type")
    nullable: bool = Field(default=True)
    is_list: bool = Field(default=False)
    default: str | None = None
    source: str | None = None
    container: str | None = None
    container_property: str | None = None
    view: str | None = None
    view_property: str | None = None
    index: str | None = None
    constraint: str | None = None


class DMSContainer(SheetEntity):
    container: str
    description: str | None = None
    constraint: str | None = None


class DMSView(SheetEntity):
    view: str
    description: str | None = None
    implements: list[str] | None = None


class DMSRules(BaseRules):
    metadata: DMSArchitectMetadata
    properties: SheetList
    containers: SheetList[DMSContainer] | None = None
    views: SheetList[DMSView] | None = None
