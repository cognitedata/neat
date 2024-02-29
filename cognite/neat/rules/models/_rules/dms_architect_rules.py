import abc
import math
import re
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import ViewPropertyApply
from pydantic import Field, field_validator, model_validator
from rdflib import Namespace

from cognite.neat.rules.models._rules.domain_rules import DomainRules

from ._types import (
    CdfValueType,
    ClassEntity,
    ClassType,
    ContainerEntity,
    ContainerListType,
    ContainerType,
    DMSValueType,
    ExternalIdType,
    ParentClassEntity,
    PropertyType,
    StrListType,
    Undefined,
    VersionType,
    ViewEntity,
    ViewListType,
    ViewType,
    XSDValueType,
)
from .base import BaseMetadata, BaseRules, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms_schema import DMSSchema

if TYPE_CHECKING:
    from .information_rules import InformationRules


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
    name: str | None = Field(
        None,
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(None, min_length=1, max_length=1024)
    external_id: ExternalIdType = Field(alias="externalId")
    version: VersionType
    creator: StrListType
    created: datetime = Field(
        description=("Date of the data model creation"),
    )
    updated: datetime = Field(
        description=("Date of the data model update"),
    )

    @field_validator("description", mode="before")
    def nan_as_none(cls, value):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    def as_space(self) -> dm.SpaceApply:
        return dm.SpaceApply(
            space=self.space,
        )

    def as_data_model(self) -> dm.DataModelApply:
        return dm.DataModelApply(
            space=self.space,
            external_id=self.external_id,
            name=self.name or None,
            version=self.version or "missing",
            description=f"{self.description} Creator: {', '.join(self.creator)}",
            views=[],
        )

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSMetadata":
        description = None
        if data_model.description and (description_match := re.search(r"Creator: (.+)", data_model.description)):
            creator = description_match.group(1).split(", ")
            data_model.description.replace(f" Creator: {', '.join(creator)}", "")
        elif data_model.description:
            creator = ["NEAT"]
            description = data_model.description
        else:
            description = "Missing description"

        return cls(
            schema_=SchemaCompleteness.complete,
            space=data_model.space,
            name=data_model.name or None,
            description=description,
            external_id=data_model.external_id,
            version=data_model.version,
            creator=creator,
            created=datetime.now(),
            updated=datetime.now(),
        )


class DMSProperty(SheetEntity):
    class_: ClassType = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    relation: Literal["direct", "multiedge"] | None = Field(None, alias="Relation")
    value_type: CdfValueType = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None | None = Field(None, alias="Default")
    source: str | None = Field(None, alias="Source")
    container: ContainerType | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: ViewType = Field(alias="View")
    view_property: str = Field(alias="ViewProperty")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")


class DMSContainer(SheetEntity):
    class_: ClassType | None = Field(None, alias="Class")
    container: ContainerType = Field(alias="Container")
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
    class_: ClassType | None = Field(None, alias="Class")
    view: ViewType = Field(alias="View")
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
    views: SheetList[DMSView] = Field(alias="Views")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")

    @model_validator(mode="after")
    def set_default_space_and_version(self) -> "DMSRules":
        default_space = self.metadata.space
        default_view_version = "1"
        for entity in self.properties:
            if entity.container and entity.container.space is Undefined:
                entity.container = ContainerEntity(prefix=default_space, suffix=entity.container.external_id)
            if entity.view and (entity.view.space is Undefined or entity.view.version is None):
                entity.view = ViewEntity(
                    prefix=default_space if entity.view.space is Undefined else entity.view.space,
                    suffix=entity.view.external_id,
                    version=default_view_version if entity.view.version is None else entity.view.version,
                )
            if isinstance(entity.value_type, ViewEntity) and (
                entity.value_type.space is Undefined or entity.value_type.version is None
            ):
                entity.value_type = ViewEntity(
                    prefix=default_space if entity.value_type.space is Undefined else entity.value_type.space,
                    suffix=entity.value_type.suffix,
                    version=default_view_version if entity.value_type.version is None else entity.value_type.version,
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
            if view.view.space is Undefined or view.view.version is None:
                view.view = ViewEntity(
                    prefix=default_space if view.view.space is Undefined else view.view.space,
                    suffix=view.view.external_id,
                    version=default_view_version if view.view.version is None else view.view.version,
                )
            view.implements = [
                (
                    ViewEntity(
                        prefix=default_space if parent.space is Undefined else parent.space,
                        suffix=parent.external_id,
                        version=default_view_version if parent.version is None else parent.version,
                    )
                    if parent.space is Undefined or parent.version is None
                    else parent
                )
                for parent in view.implements or []
            ] or None

        return self

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

    def as_schema(self) -> DMSSchema:
        return _DMSExporter(self).to_schema()

    def as_information_architect_rules(self) -> "InformationRules":
        return _DMSRulesConverter(self).as_information_architect_rules()

    def as_dms_architect_rules(self) -> DomainRules:
        return _DMSRulesConverter(self).as_domain_rules()


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
                if isinstance(prop.value_type, DMSValueType):
                    type_cls = prop.value_type.dms
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
                        type_ = cast(CognitePropertyType, type_cls())
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
                            # Probably we will not have this case, but just in case
                            source = dm.ViewId(default_space, prop.value_type.suffix, default_version)

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
                        # CRITICAL COMMENT: NOT SURE WHY IS THIS ALLOWED!?
                        source = dm.ViewId(default_space, prop.value_type.suffix, default_version)
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


class _DMSRulesConverter:
    def __init__(self, dms: DMSRules):
        self.dms = dms

    def as_domain_rules(self) -> "DomainRules":
        raise NotImplementedError("DomainRules not implemented yet")

    def as_information_architect_rules(
        self,
        created: datetime | None = None,
        updated: datetime | None = None,
        name: str | None = None,
        namespace: Namespace | None = None,
    ) -> "InformationRules":
        from .information_rules import InformationClass, InformationMetadata, InformationProperty, InformationRules

        dms = self.dms.metadata
        prefix = dms.space

        metadata = InformationMetadata(
            schema_=dms.schema_,
            prefix=prefix,
            namespace=namespace or Namespace(f"https://purl.orgl/neat/{prefix}/"),
            version=dms.version,
            name=name or dms.name or "Missing name",
            creator=dms.creator,
            created=dms.created or created or datetime.now(),
            updated=dms.updated or updated or datetime.now(),
        )

        classes: list[InformationClass] = [
            InformationClass(
                class_=view.view.suffix,
                description=view.description,
                parent=[
                    ParentClassEntity(prefix=implented_view.prefix, suffix=implented_view.suffix)
                    for implented_view in view.implements or []
                ],
            )
            for view in self.dms.views
        ]

        properties: list[InformationProperty] = []
        value_type: XSDValueType | ClassEntity | str
        for property_ in self.dms.properties:
            if isinstance(property_.value_type, DMSValueType):
                value_type = cast(DMSValueType, property_.value_type).xsd
            elif isinstance(property_.value_type, ViewEntity):
                value_type = ClassEntity(
                    prefix=property_.value_type.prefix,
                    suffix=property_.value_type.suffix,
                )
            else:
                raise ValueError(f"Unsupported value type: {property_.value_type.type_}")

            properties.append(
                InformationProperty(
                    class_=cast(ViewEntity, property_.view).suffix,
                    property_=property_.view_property,
                    value_type=cast(XSDValueType | ClassEntity, value_type),
                    description=property_.description,
                    min_count=0 if property_.nullable or property_.nullable is None else 1,
                    max_count=float("inf") if property_.is_list or property_.nullable is None else 1,
                )
            )

        return InformationRules(
            metadata=metadata,
            properties=SheetList[InformationProperty](data=properties),
            classes=SheetList[InformationClass](data=classes),
        )
