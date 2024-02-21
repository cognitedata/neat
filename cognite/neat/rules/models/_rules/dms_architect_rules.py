import abc
from datetime import datetime
from itertools import groupby
from typing import Any, ClassVar, Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType
from pydantic import Field, field_validator

from cognite.neat.rules.models._rules.information_rules import InformationMetadata

from ._types import ExternalIdType, StrListType, StrOrListType, VersionType
from .base import BaseMetadata, BaseRules, RoleTypes, SheetEntity, SheetList
from .dms_schema import DMSSchema
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


class DMSMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms_architect
    schema_: Literal["Complete", "Partial"] = Field(alias="schema")
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

    def as_space(self) -> dm.SpaceApply:
        return dm.SpaceApply(
            space=self.space,
        )

    def as_data_model(self) -> dm.DataModelApply:
        return dm.DataModelApply(
            space=self.space,
            external_id=self.external_id,
            version=self.version or "missing",
            description=f"Contributor: {', '.join(self.contributor)}",
            views=[],
        )


class DMSProperty(SheetEntity):
    class_: str = Field(alias="Class")
    property_: str = Field(alias="Property")
    description: str | None = Field(None, alias="Description")
    value_type: type[PropertyType] | str = Field(alias="Value Type")
    relation: str | None = Field(None, alias="Relation")
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
    class_: str | None = Field(None, alias="Class")
    container: str = Field(alias="Container")
    description: str | None = Field(None, alias="Description")
    constraint: str | None = Field(None, alias="Constraint")


class DMSView(SheetEntity):
    class_: str | None = Field(None, alias="Class")
    view: str = Field(alias="View")
    description: str | None = Field(None, alias="Description")
    implements: StrListType | None = Field(None, alias="Implements")


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    views: SheetList[DMSView] | None = Field(None, alias="Views")

    def as_schema(self) -> DMSSchema:
        version = self.metadata.version or "missing"
        space = self.metadata.space
        data_model = self.metadata.as_data_model()
        containers = dm.ContainerApplyList([])
        container_properties = sorted(
            [prop for prop in self.properties if prop.container and prop.container_property],
            key=lambda p: p.container or "",
        )
        for container_external_id, properties in groupby(container_properties, key=lambda p: p.container):
            container = dm.ContainerApply(
                space=space,
                external_id=container_external_id,
                properties={
                    prop.container_property: dm.ContainerProperty(
                        type=(
                            type_()
                            if (type_ := _PropertyType_by_name.get(prop.value_type.casefold()))
                            else dm.DirectRelation()
                        )
                        if isinstance(prop.value_type, str)
                        else prop.value_type(),
                        nullable=prop.nullable or True,
                        default_value=prop.default,
                    )
                    for prop in properties
                    if prop.container_property
                },
            )
            containers.append(container)

        view_by_ids: dict[dm.ViewId, dm.ViewApply] = {}
        view_properties = sorted(
            [prop for prop in self.properties if prop.view and prop.view_property], key=lambda p: p.view or ""
        )

        def _create_mapped_property(property_: DMSProperty) -> dm.MappedPropertyApply:
            if not (property_.container and property_.container_property):
                raise ValueError("Mapped property must have container and container_property")
            return dm.MappedPropertyApply(
                container=dm.ContainerId(space, property_.container),
                container_property_identifier=property_.container_property,
            )

        def _create_connection_property(property_: DMSProperty) -> dm.MultiEdgeConnectionApply:
            if property_.relation != "multiedge":
                raise NotImplementedError(f"Currently only multiedge is supported, not {property_.relation}")
            if not isinstance(property_.value_type, str):
                raise ValueError("Only string value type is supported for connection properties")
            return dm.MultiEdgeConnectionApply(
                type=dm.DirectRelationReference(
                    space=space,
                    external_id=f"{property_.view}.{property_.view_property}",
                ),
                source=dm.ViewId(space, property_.value_type, version),
            )

        for view_external_id, properties in groupby(view_properties, key=lambda p: p.view):
            view = dm.ViewApply(
                space=space,
                external_id=view_external_id,
                version=version,
                properties={
                    prop.view_property: (
                        _create_mapped_property(prop) if prop.container else _create_connection_property(prop)
                    )
                    for prop in properties
                    if prop.view_property
                },
            )
            view_by_ids[view.as_id()] = view
            if data_model.views is None:
                data_model.views = [view.as_id()]
            else:
                data_model.views.append(view.as_id())

        for dms_view in self.views or []:
            if dms_view.implements:
                view_id = dm.ViewId(space, dms_view.view, version=version)
                if view_id in view_by_ids:
                    view_by_ids[view_id].implements = [
                        dm.ViewId(space, parent, version=version) for parent in dms_view.implements
                    ]

        return DMSSchema(
            space=self.metadata.as_space(),
            model=data_model,
            views=dm.ViewApplyList(view_by_ids.values()),
            containers=containers,
        )
