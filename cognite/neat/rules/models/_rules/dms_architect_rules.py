import abc
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, ClassVar, Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import ViewPropertyApply
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from cognite.neat.rules.models._rules.information_rules import InformationMetadata

from ._types import (
    ContainerEntity,
    ContainerListType,
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
from .base import BaseMetadata, BaseRules, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
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
    schema_: SchemaCompleteness = Field(alias="schema")
    space: ExternalIdType
    external_id: ExternalIdType = Field(alias="externalId")
    version: VersionType | None
    contributor: StrListType | None = Field(
        default=None,
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
            description=f"Contributor: {', '.join(self.contributor or [])}",
            views=[],
        )

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSMetadata":
        if data_model.description and (description_match := re.search(r"Contributor: (.+)", data_model.description)):
            contributor = description_match.group(1).split(", ")
        else:
            contributor = []

        return cls(
            schema_=SchemaCompleteness.complete,
            space=data_model.space,
            external_id=data_model.external_id,
            version=data_model.version,
            contributor=contributor,
        )


class DMSProperty(SheetEntity):
    class_: str = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    description: str | None = Field(None, alias="Description")
    relation: Literal["direct", "multiedge"] | None = Field(None, alias="Relation")
    value_type: ViewEntity | str = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None | None = Field(None, alias="Default")
    source: str | None = Field(None, alias="Source")
    container: ContainerType | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: ViewType | None = Field(None, alias="View")
    view_property: str | None = Field(None, alias="ViewProperty")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")

    @field_validator("value_type", mode="before")
    def parse_value_type(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str):
            return value

        if info.data.get("relation"):
            # If the property is a relation (direct or edge), the value type should be a ViewEntity
            # for the target view (aka the object in a triple)
            return ViewEntity.from_raw(value)
        return value

    @field_serializer("value_type", when_used="unless-none")
    def serialize_value_type(self, value: Any) -> Any:
        if isinstance(value, ViewEntity):
            return value.versioned_id
        return value

    @field_validator("value_type", mode="after")
    def validate_value_type(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str) or info.data.get("relation") is not None:
            return value
        value = value.casefold()
        if value in _PropertyType_by_name:
            return value
        raise ValueError(
            f"Value type {value} is not a valid value type for a property. "
            f"Valid types are: {_PropertyType_by_name.keys()}"
        )


class DMSContainer(SheetEntity):
    class_: str | None = Field(None, alias="Class")
    container: ContainerType = Field(alias="Container")
    description: str | None = Field(None, alias="Description")
    constraint: ContainerListType | None = Field(None, alias="Constraint")

    def as_container(self, default_space: str) -> dm.ContainerApply:
        container_id = self.container.as_id(default_space)
        constraints: dict[str, dm.Constraint] = {}
        for constraint in self.constraint or []:
            requires = dm.RequiresConstraint(constraint.as_id(default_space))
            constraints = {constraint.versioned_id: requires}

        return dm.ContainerApply(
            space=container_id.space,
            external_id=container_id.external_id,
            description=self.description,
            constraints=constraints or None,
            properties={},
        )

    @classmethod
    def from_container(cls, container: dm.ContainerApply) -> "DMSContainer":
        constraints: list[ContainerEntity] = []
        for _, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                constraints.append(ContainerEntity.from_id(constraint_obj.require))
            # UniquenessConstraint it handled in the properties
        return cls(
            class_=container.external_id,
            container=ContainerType(prefix=container.space, suffix=container.external_id),
            description=container.description,
            constraint=constraints or None,
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
            view=ViewType(prefix=view.space, suffix=view.external_id, version=view.version),
            description=view.description,
            implements=[
                ViewType(prefix=parent.space, suffix=parent.external_id, version=parent.version)
                for parent in view.implements
            ]
            or None,
        )


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    views: SheetList[DMSView] | None = Field(None, alias="Views")

    @model_validator(mode="after")
    def consistent_container_properties(self) -> "DMSRules":
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[DMSProperty]] = defaultdict(list)
        for prop in self.properties:
            if prop.container and prop.container_property:
                container_properties_by_id[(prop.container, prop.container_property)].append(prop)

        exceptions: list[str] = []
        for (container, prop_name), properties in container_properties_by_id.items():
            if len(properties) == 1:
                continue

            value_types = {prop.value_type for prop in properties if prop.value_type}
            if len(value_types) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different value types: {value_types}"
                )
            list_definitions = {prop.is_list for prop in properties if prop.is_list is not None}
            if len(list_definitions) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different "
                    f"list definitions: {list_definitions}"
                )
            nullable_definitions = {prop.nullable for prop in properties if prop.nullable is not None}
            if len(nullable_definitions) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different "
                    f"nullable definitions: {nullable_definitions}"
                )
            default_definitions = {prop.default for prop in properties if prop.default is not None}
            if len(default_definitions) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different "
                    f"default definitions: {default_definitions}"
                )
            index_definitions = {",".join(prop.index) for prop in properties if prop.index is not None}
            if len(index_definitions) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different "
                    f"index definitions: {index_definitions}"
                )
            constraint_definitions = {",".join(prop.constraint) for prop in properties if prop.constraint is not None}
            if len(constraint_definitions) > 1:
                exceptions.append(
                    f"Container {container}.{prop_name} is defined with different "
                    f"unique constraint definitions: {constraint_definitions}"
                )

            # This sets the container definition for all the properties where it is not defined.
            # This allows the user to define the container only once.
            value_type = value_types.pop()
            list_definition = list_definitions.pop() if list_definitions else None
            nullable_definition = nullable_definitions.pop() if nullable_definitions else None
            default_definition = default_definitions.pop() if default_definitions else None
            index_definition = index_definitions.pop().split(",") if index_definitions else None
            constraint_definition = constraint_definitions.pop().split(",") if constraint_definitions else None
            for prop in properties:
                prop.value_type = value_type
                prop.is_list = prop.is_list or list_definition
                prop.nullable = prop.nullable or nullable_definition
                prop.default = prop.default or default_definition
                prop.index = prop.index or index_definition
                prop.constraint = prop.constraint or constraint_definition

        if exceptions:
            exception_str = "\n".join(exceptions)
            raise ValueError(f"Inconsistent container(s): {exception_str}")
        return self

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
            container.constraint = [
                (
                    ContainerEntity(prefix=default_space, suffix=constraint.external_id)
                    if constraint.space is Undefined
                    else constraint
                )
                for constraint in container.constraint or []
            ] or None
        for view in self.views or []:
            if view.view.space is Undefined:
                view.view = ViewEntity(prefix=default_space, suffix=view.view.external_id, version=view.view.version)
            view.implements = [
                (
                    ViewEntity(prefix=default_space, suffix=parent.external_id, version=parent.version)
                    if parent.space is Undefined
                    else parent
                )
                for parent in view.implements or []
            ] or None

    def set_default_version(self, default_version: str = "1") -> None:
        """This replaces all undefined versions with"""
        for prop in self.properties:
            if prop.view and prop.view.version is None:
                prop.view = ViewEntity(prefix=prop.view.space, suffix=prop.view.external_id, version=default_version)
        for view in self.views or []:
            if view.view.version is None:
                view.view = ViewEntity(prefix=view.view.space, suffix=view.view.external_id, version=default_version)
            view.implements = [
                (
                    ViewEntity(prefix=parent.space, suffix=parent.external_id, version=default_version)
                    if parent.version is None
                    else parent
                )
                for parent in view.implements or []
            ] or None

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
                if isinstance(prop.value_type, str):
                    type_cls = _PropertyType_by_name.get(prop.value_type.casefold(), dm.DirectRelation)
                else:
                    type_cls = dm.DirectRelation
                if type_cls is dm.DirectRelation:
                    container.properties[prop.container_property] = dm.ContainerProperty(
                        type=dm.DirectRelation(),
                        nullable=prop.nullable if prop.nullable is not None else True,
                        default_value=prop.default,
                    )
                else:
                    type_: CognitePropertyType
                    if issubclass(type_cls, ListablePropertyType):
                        type_ = type_cls(is_list=prop.is_list or False)
                    else:
                        type_ = type_cls()
                    container.properties[prop.container_property] = dm.ContainerProperty(
                        type=type_,
                        nullable=prop.nullable if prop.nullable is not None else True,
                        default_value=prop.default,
                    )

            uniqueness_properties: dict[str, set[str]] = defaultdict(set)
            for prop in container_properties:
                if prop.container_property is not None:
                    for constraint in prop.constraint or []:
                        uniqueness_properties[constraint].add(prop.container_property)
            for constraint_name, properties in uniqueness_properties.items():
                container.constraints = container.constraints or {}
                container.constraints[constraint_name] = dm.UniquenessConstraint(properties=list(properties))

            index_properties: dict[str, set[str]] = defaultdict(set)
            for prop in container_properties:
                if prop.container_property is not None:
                    for index in prop.index or []:
                        index_properties[index].add(prop.container_property)
            for index_name, properties in index_properties.items():
                container.indexes = container.indexes or {}
                container.indexes[index_name] = BTreeIndex(properties=list(properties))

        for view in views:
            view_id = view.as_id()
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property: ViewPropertyApply
                if prop.container and prop.container_property and prop.view_property:
                    if prop.relation == "direct":
                        if isinstance(prop.value_type, ViewEntity):
                            source = prop.value_type.as_id(default_space, default_version)
                        else:
                            source = dm.ViewId(default_space, prop.value_type, default_version)

                        view_property = dm.MappedPropertyApply(
                            container=prop.container.as_id(default_space),
                            container_property_identifier=prop.container_property,
                            source=source,
                        )
                    else:
                        view_property = dm.MappedPropertyApply(
                            container=prop.container.as_id(default_space),
                            container_property_identifier=prop.container_property,
                        )
                elif prop.view and prop.view_property:
                    if not prop.relation:
                        continue
                    if prop.relation != "multiedge":
                        raise NotImplementedError(f"Currently only multiedge is supported, not {prop.relation}")
                    if isinstance(prop.value_type, ViewEntity):
                        source = prop.value_type.as_id(default_space, default_version)
                    else:
                        source = dm.ViewId(default_space, prop.value_type, default_version)
                    view_property = dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference(
                            space=default_space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        ),
                        source=source,
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
