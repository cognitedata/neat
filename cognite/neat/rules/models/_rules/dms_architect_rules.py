import abc
import re
from collections import defaultdict
from datetime import datetime
from typing import ClassVar, Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import ViewPropertyApply
from pydantic import Field

from cognite.neat.rules.models._rules.information_rules import InformationMetadata

from ._types import (
    ContainerEntity,
    ContainerType,
    ExternalIdType,
    PropertyType,
    StrListType,
    Undefined,
    VersionType,
    ViewEntity,
    ViewListType,
    ViewType,
)
from .base import BaseMetadata, BaseRules, RoleTypes, SheetEntity, SheetList
from .dms_schema import DMSSchema
from .domain_rules import DomainMetadata

subclasses = list(CognitePropertyType.__subclasses__())
_PropertyType_by_name: dict[str, type[CognitePropertyType]] = {}
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
    schema_: Literal["complete", "partial", "extended"] = Field(alias="schema")
    space: ExternalIdType
    external_id: ExternalIdType = Field(alias="externalId")
    version: VersionType | None
    contributor: StrListType = Field(
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

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSMetadata":
        if data_model.description and (description_match := re.search(r"Contributor: (.+)", data_model.description)):
            contributor = description_match.group(1).split(", ")
        else:
            contributor = []

        return cls(
            schema_="complete",
            space=data_model.space,
            external_id=data_model.external_id,
            version=data_model.version,
            contributor=contributor,
        )


class DMSProperty(SheetEntity):
    class_: str = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    description: str | None = Field(None, alias="Description")
    value_type: str = Field(alias="Value Type")
    relation: str | None = Field(None, alias="Relation")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None | None = Field(None, alias="Default")
    source: str | None = Field(None, alias="Source")
    container: ContainerType | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: ViewType | None = Field(None, alias="View")
    view_property: str | None = Field(None, alias="ViewProperty")
    index: str | None = Field(None, alias="Index")
    constraint: str | None = Field(None, alias="Constraint")


class DMSContainer(SheetEntity):
    class_: str | None = Field(None, alias="Class")
    container: ContainerType = Field(alias="Container")
    description: str | None = Field(None, alias="Description")
    constraint: ContainerType | None = Field(None, alias="Constraint")

    def as_container(self, default_space: str) -> dm.ContainerApply:
        container_id = self.container.as_id(default_space)
        return dm.ContainerApply(
            space=container_id.space,
            external_id=container_id.external_id,
            description=self.description,
            properties={},
        )

    @classmethod
    def from_container(cls, container: dm.ContainerApply) -> "DMSContainer":
        # Todo - add constraint
        if container.constraints:
            raise NotImplementedError("Constraints are not yet supported")

        return cls(
            class_=container.external_id,
            container=ContainerType(prefix=container.space, suffix=container.external_id),
            description=container.description,
            constraint=None,
        )


class DMSView(SheetEntity):
    class_: str | None = Field(None, alias="Class")
    view: ViewType = Field(alias="View")
    description: str | None = Field(None, alias="Description")
    implements: ViewListType | None = Field(None, alias="Implements")

    def as_view(self, default_space: str, default_version: str) -> dm.ViewApply:
        view_id = self.view.as_id(default_space, default_version)
        return dm.ViewApply(
            space=view_id.space,
            external_id=view_id.external_id,
            version=view_id.version or default_version,
            description=self.description,
            implements=[parent.as_id(default_space, default_version) for parent in self.implements or []] or None,
            properties={},
        )

    @classmethod
    def from_view(cls, view: dm.ViewApply) -> "DMSView":
        return cls(
            class_=view.external_id,
            view=ViewType(prefix=view.space, suffix=view.external_id),
            description=view.description,
            implements=[ViewType(prefix=parent.space, suffix=parent.external_id) for parent in view.implements] or None,
        )


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    views: SheetList[DMSView] | None = Field(None, alias="Views")

    def set_default_space(self) -> None:
        """This replaces all undefined spaces with the default space from the metadata."""
        default_space = self.metadata.space
        for entity in self.properties:
            if entity.container and entity.container.space is Undefined:
                entity.container = ContainerEntity(prefix=default_space, suffix=entity.container.external_id)
            if entity.view and entity.view.space is Undefined:
                entity.view = ViewEntity(
                    prefix=default_space, suffix=entity.view.external_id, version=entity.view.version
                )
        for container in self.containers or []:
            if container.container.space is Undefined:
                container.container = ContainerEntity(prefix=default_space, suffix=container.container.external_id)
        for view in self.views or []:
            if view.view.space is Undefined:
                view.view = ViewEntity(prefix=default_space, suffix=view.view.external_id, version=view.view.version)

    def set_default_version(self, default_version: str = "1") -> None:
        """This replaces all undefined versions with"""
        for prop in self.properties:
            if prop.view and prop.view.version is None:
                prop.view = ViewEntity(prefix=prop.view.space, suffix=prop.view.external_id, version=default_version)
        for view in self.views or []:
            if view.view.version is None:
                view.view = ViewEntity(prefix=view.view.space, suffix=view.view.external_id, version=default_version)

    def as_schema(self) -> DMSSchema:
        return _DMSExporter(self).to_schema()


class _DMSExporter:
    """The DMS Exporter is responsible for exporting the DMSRules to a DMSSchema.

    This kept in this location such that it can be used by the DMSRules to validate the schema.
    (This module cannot have a dependency on the exporter module, as it would create a circular dependency.)

    """

    def __init__(self, rules: DMSRules):
        self.rules = rules

    def to_schema(self) -> DMSSchema:
        default_version = "1"
        default_space = self.rules.metadata.space
        data_model = self.rules.metadata.as_data_model()

        containers = dm.ContainerApplyList(
            [dms_container.as_container(default_space) for dms_container in self.rules.containers or []]
        )
        views = dm.ViewApplyList(
            [dms_view.as_view(default_space, default_version) for dms_view in self.rules.views or []]
        )

        data_model.views = list(views.as_ids())

        container_properties_by_id, view_properties_by_id = self._gather_properties(default_space, default_version)

        for container in containers:
            container_id = container.as_id()
            if not (container_properties := container_properties_by_id.get(container_id)):
                continue
            for prop in container_properties:
                if prop.container_property is None:
                    continue
                type_cls = _PropertyType_by_name.get(prop.value_type.casefold(), dm.DirectRelation)
                type_: CognitePropertyType
                if issubclass(type_cls, ListablePropertyType):
                    type_ = type_cls(is_list=prop.is_list or False)
                else:
                    type_ = type_cls()

                container.properties[prop.container_property] = dm.ContainerProperty(
                    type=type_,
                    nullable=prop.nullable or True,
                    default_value=prop.default,
                )

        for view in views:
            view_id = view.as_id()
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property: ViewPropertyApply
                if prop.container and prop.container_property and prop.view_property:
                    view_property = dm.MappedPropertyApply(
                        container=prop.container.as_id(default_space),
                        container_property_identifier=prop.container_property,
                    )
                elif prop.view and prop.view_property:
                    if not prop.relation:
                        continue
                    if prop.relation != "multiedge":
                        raise NotImplementedError(f"Currently only multiedge is supported, not {prop.relation}")
                    view_property = dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference(
                            space=default_space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        ),
                        source=dm.ViewId(default_space, prop.value_type, default_version),
                        direction="outwards",
                    )
                else:
                    continue
                view.properties[prop.view_property] = view_property

        return DMSSchema(
            spaces=dm.SpaceApplyList([self.rules.metadata.as_space()]),
            data_models=dm.DataModelApplyList([data_model]),
            views=views,
            containers=containers,
        )

    def _gather_properties(
        self, default_space: str, default_version: str
    ) -> tuple[dict[dm.ContainerId, list[DMSProperty]], dict[dm.ViewId, list[DMSProperty]]]:
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in self.rules.properties:
            if prop.container and prop.container_property:
                container_id = prop.container.as_id(default_space)
                container_properties_by_id[container_id].append(prop)
            if prop.view and prop.view_property:
                view_id = prop.view.as_id(default_space, default_version)
                view_properties_by_id[view_id].append(prop)
        return container_properties_by_id, view_properties_by_id
