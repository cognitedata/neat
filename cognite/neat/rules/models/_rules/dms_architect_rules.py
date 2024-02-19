import abc
from datetime import datetime
from typing import Any, ClassVar

from cognite.client.data_classes.data_modeling import PropertyType
from pydantic import Field, field_validator

from cognite.neat.rules.models._rules.information_rules import InformationMetadata

from ._types import ExternalIdType, StrListType, StrOrListType, VersionType
from .base import BaseMetadata, BaseRules, RoleTypes, SheetEntity, SheetList
from .domain_rules import DomainMetadata

subclasses = list(PropertyType.__subclasses__())
_PropertyType_by_name: dict[str, type[PropertyType]] = {}
for subclass in subclasses:
    subclasses.extend(subclass.__subclasses__())
    if abc.ABC in subclass.__bases__:
        continue
    try:
        _PropertyType_by_name[subclass._type.casefold()] = subclass
    except AttributeError:
        ...
del subclasses  # cleanup namespace


class DMSArchitectMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms_architect
    space: ExternalIdType
    external_id: ExternalIdType = Field(alias="externalId")
    version: VersionType | None
    contributor: StrOrListType = Field(
        description=(
            "List of contributors to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )

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
        external_id: str | None = None,
        version: str | None = None,
        contributor: str | list[str] | None = None,
        created: datetime | None = None,
        updated: datetime | None = None,
    ):
        information = InformationMetadata.from_domain_expert_metadata(
            metadata, None, None, version, contributor, created, updated
        ).model_dump()

        return cls.from_information_architect_metadata(information, space, external_id)


class DMSProperty(SheetEntity):
    class_: str = Field(alias="Class")
    property_: str = Field(alias="Property")
    description: str | None = Field(None, alias="Description")
    value_type: type[PropertyType] | str = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | None = Field(None, alias="Default")
    source: str | None = Field(None, alias="Source")
    container: str | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: str | None = Field(None, alias="View")
    view_property: str | None = Field(None, alias="ViewProperty")
    index: str | None = Field(None, alias="Index")
    constraint: str | None = Field(None, alias="Constraint")

    @field_validator("value_type", mode="before")
    def to_type(cls, value: Any) -> Any:
        if isinstance(value, str) and value.casefold() in _PropertyType_by_name:
            return _PropertyType_by_name[value.casefold()]
        return value


class DMSContainer(SheetEntity):
    class_: str = Field(alias="Class")
    container: str = Field(alias="Container")
    description: str | None = Field(None, alias="Description")
    constraint: str | None = Field(None, alias="Constraint")


class DMSView(SheetEntity):
    class_: str = Field(alias="Class")
    view: str = Field(alias="View")
    description: str | None = Field(None, alias="Description")
    implements: StrListType | None = Field(None, alias="Implements")


class DMSRules(BaseRules):
    metadata: DMSArchitectMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    views: SheetList[DMSView] | None = Field(None, alias="Views")
