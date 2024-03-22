import abc
import math
import re
import warnings
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import SingleReverseDirectRelationApply, ViewPropertyApply
from pydantic import Field, field_validator, model_serializer, model_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo
from rdflib import Namespace

import cognite.neat.rules.issues.spreadsheet
from cognite.neat.rules import issues
from cognite.neat.rules.models._rules.domain_rules import DomainRules
from cognite.neat.utils.text import to_camel

from ._types import (
    CdfValueType,
    ClassEntity,
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
    ViewPropEntity,
    ViewType,
    XSDValueType,
)
from .base import BaseMetadata, BaseRules, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms_schema import DMSSchema, PipelineSchema

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
    # MyPy does not account for the field validator below that sets the default value
    default_view_version: VersionType = Field(None)  # type: ignore[assignment]

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("schema_", mode="plain")
    def as_enum(cls, value: str) -> SchemaCompleteness:
        return SchemaCompleteness(value)

    @model_validator(mode="before")
    def set_default_view_version_if_missing(cls, values):
        if "default_view_version" not in values:
            values["default_view_version"] = values["version"]
        return values

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
        suffix = f"Creator: {', '.join(self.creator)}"
        if self.description:
            description = f"{self.description} Creator: {', '.join(self.creator)}"
        else:
            description = suffix

        return dm.DataModelApply(
            space=self.space,
            external_id=self.external_id,
            name=self.name or None,
            version=self.version or "missing",
            description=description,
            views=[],
        )

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSMetadata":
        description = None
        if data_model.description and (description_match := re.search(r"Creator: (.+)", data_model.description)):
            creator = description_match.group(1).split(", ")
            data_model.description.replace(f" Creator: {', '.join(creator)}", "")
        elif data_model.description:
            creator = ["MISSING"]
            description = data_model.description
        else:
            creator = ["MISSING"]
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
    property_: PropertyType = Field(alias="Property")
    relation: Literal["direct", "reversedirect", "multiedge"] | None = Field(None, alias="Relation")
    value_type: CdfValueType = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None = Field(None, alias="Default")
    reference: str | None = Field(None, alias="Reference")
    container: ContainerType | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: ViewType = Field(alias="View")
    view_property: str = Field(alias="ViewProperty")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")

    @field_validator("nullable")
    def direct_relation_must_be_nullable(cls, value: Any, info: ValidationInfo) -> None:
        if info.data.get("relation") == "direct" and value is False:
            raise ValueError("Direct relation must be nullable")
        return value

    @field_validator("container_property", "container")
    def reverse_direct_relation_has_no_container(cls, value, info: ValidationInfo) -> None:
        if info.data.get("relation") == "reversedirect" and value is not None:
            raise ValueError(f"Reverse direct relation must not have container or container property, got {value}")
        return value

    @field_validator("value_type", mode="after")
    def relations_value_type(cls, value: CdfValueType, info: ValidationInfo) -> CdfValueType:
        if (relation := info.data["relation"]) is None:
            return value
        if not isinstance(value, ViewPropEntity):
            raise ValueError(f"Relations must have a value type that points to another view, got {value}")
        if relation == "reversedirect" and value.property_ is None:
            raise ValueError(
                "Reverse direct relation must set what it is the reverse property of. "
                f"Which property in {value.versioned_id} is this the reverse of? Expecting"
                f"{value.versioned_id}:<property>"
            )
        return value


class DMSContainer(SheetEntity):
    container: ContainerType = Field(alias="Container")
    constraint: ContainerListType | None = Field(None, alias="Constraint")

    def as_container(self, default_space: str, standardize_casing: bool = True) -> dm.ContainerApply:
        container_id = self.container.as_id(default_space, standardize_casing)
        constraints: dict[str, dm.Constraint] = {}
        for constraint in self.constraint or []:
            requires = dm.RequiresConstraint(constraint.as_id(default_space))
            constraints[f"{constraint.space}_{constraint.external_id}"] = requires

        return dm.ContainerApply(
            space=container_id.space,
            external_id=container_id.external_id,
            name=self.name or None,
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
            class_=ClassEntity(prefix=container.space, suffix=container.external_id),
            container=ContainerType(prefix=container.space, suffix=container.external_id),
            name=container.name or None,
            description=container.description,
            constraint=constraints or None,
        )


class DMSView(SheetEntity):
    view: ViewType = Field(alias="View")
    implements: ViewListType | None = Field(None, alias="Implements")
    in_model: bool = Field(True, alias="InModel")

    def as_view(self, default_space: str, default_version: str, standardize_casing: bool = True) -> dm.ViewApply:
        view_id = self.view.as_id(default_space, default_version, standardize_casing)
        return dm.ViewApply(
            space=view_id.space,
            external_id=view_id.external_id,
            version=view_id.version or default_version,
            name=self.name or None,
            description=self.description,
            implements=[
                parent.as_id(default_space, default_version, standardize_casing) for parent in self.implements or []
            ]
            or None,
            properties={},
        )

    @classmethod
    def from_view(cls, view: dm.ViewApply) -> "DMSView":
        return cls(
            class_=ClassEntity(prefix=view.space, suffix=view.external_id),
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
        default_view_version = self.metadata.default_view_version
        for entity in self.properties:
            if entity.class_.prefix is Undefined or entity.class_.version is None:
                entity.class_ = ClassEntity(
                    prefix=default_space if entity.class_.prefix is Undefined else entity.class_.prefix,
                    suffix=entity.class_.suffix,
                    version=default_view_version if entity.class_.version is None else entity.class_.version,
                )
            if entity.container and entity.container.space is Undefined:
                entity.container = ContainerEntity(prefix=default_space, suffix=entity.container.external_id)

            if entity.view and (entity.view.space is Undefined or entity.view.version is None):
                entity.view = ViewEntity(
                    prefix=default_space if entity.view.space is Undefined else entity.view.space,
                    suffix=entity.view.external_id,
                    version=default_view_version if entity.view.version is None else entity.view.version,
                )
            if isinstance(entity.value_type, ViewPropEntity) and (
                entity.value_type.space is Undefined or entity.value_type.version is None
            ):
                entity.value_type = ViewPropEntity(
                    prefix=default_space if entity.value_type.space is Undefined else entity.value_type.space,
                    suffix=entity.value_type.suffix,
                    version=default_view_version if entity.value_type.version is None else entity.value_type.version,
                    property_=entity.value_type.property_,
                )

        for container in self.containers or []:
            if container.class_.prefix is Undefined:
                container.class_ = ClassEntity(prefix=default_space, suffix=container.class_.suffix)
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
            if view.class_.prefix is Undefined or view.class_.version is None:
                view.class_ = ClassEntity(
                    prefix=default_space if view.class_.prefix is Undefined else view.class_.prefix,
                    suffix=view.class_.suffix,
                    version=default_view_version if view.class_.version is None else view.class_.version,
                )

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
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[tuple[int, DMSProperty]]] = defaultdict(list)
        for prop_no, prop in enumerate(self.properties):
            if prop.container and prop.container_property:
                container_properties_by_id[(prop.container, prop.container_property)].append((prop_no, prop))

        errors: list[cognite.neat.rules.issues.spreadsheet.InconsistentContainerDefinitionError] = []
        for (container, prop_name), properties in container_properties_by_id.items():
            if len(properties) == 1:
                continue
            container_id = container.as_id(self.metadata.space)
            row_numbers = {prop_no for prop_no, _ in properties}
            value_types = {prop.value_type for _, prop in properties if prop.value_type}
            if len(value_types) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiValueTypeError(
                        container_id, prop_name, row_numbers, {str(v) for v in value_types}
                    )
                )
            list_definitions = {prop.is_list for _, prop in properties if prop.is_list is not None}
            if len(list_definitions) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiValueIsListError(
                        container_id, prop_name, row_numbers, list_definitions
                    )
                )
            nullable_definitions = {prop.nullable for _, prop in properties if prop.nullable is not None}
            if len(nullable_definitions) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiNullableError(
                        container_id, prop_name, row_numbers, nullable_definitions
                    )
                )
            default_definitions = {prop.default for _, prop in properties if prop.default is not None}
            if len(default_definitions) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiDefaultError(
                        container_id, prop_name, row_numbers, list(default_definitions)
                    )
                )
            index_definitions = {",".join(prop.index) for _, prop in properties if prop.index is not None}
            if len(index_definitions) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiIndexError(
                        container_id, prop_name, row_numbers, index_definitions
                    )
                )
            constraint_definitions = {
                ",".join(prop.constraint) for _, prop in properties if prop.constraint is not None
            }
            if len(constraint_definitions) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiUniqueConstraintError(
                        container_id, prop_name, row_numbers, constraint_definitions
                    )
                )

            # This sets the container definition for all the properties where it is not defined.
            # This allows the user to define the container only once.
            value_type = next(iter(value_types))
            list_definition = next(iter(list_definitions)) if list_definitions else None
            nullable_definition = next(iter(nullable_definitions)) if nullable_definitions else None
            default_definition = next(iter(default_definitions)) if default_definitions else None
            index_definition = next(iter(index_definitions)).split(",") if index_definitions else None
            constraint_definition = next(iter(constraint_definitions)).split(",") if constraint_definitions else None
            for _, prop in properties:
                prop.value_type = value_type
                prop.is_list = prop.is_list or list_definition
                prop.nullable = prop.nullable or nullable_definition
                prop.default = prop.default or default_definition
                prop.index = prop.index or index_definition
                prop.constraint = prop.constraint or constraint_definition

        if errors:
            raise issues.MultiValueError(errors)
        return self

    @model_validator(mode="after")
    def referenced_views_and_containers_are_existing(self) -> "DMSRules":
        # There two checks are done in the same method to raise all the errors at once.
        defined_views = {view.view.as_id(self.metadata.space, self.metadata.version) for view in self.views}

        errors: list[issues.NeatValidationError] = []
        for prop_no, prop in enumerate(self.properties):
            if (
                prop.view
                and (view_id := prop.view.as_id(self.metadata.space, self.metadata.version)) not in defined_views
            ):
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.NonExistingViewError(
                        column="View",
                        row=prop_no,
                        type="value_error.missing",
                        view_id=view_id,
                        msg="",
                        input=None,
                        url=None,
                    )
                )
        if self.metadata.schema_ is SchemaCompleteness.complete:
            defined_containers = {container.container.as_id(self.metadata.space) for container in self.containers or []}
            for prop_no, prop in enumerate(self.properties):
                if (
                    prop.container
                    and (container_id := prop.container.as_id(self.metadata.space)) not in defined_containers
                ):
                    errors.append(
                        cognite.neat.rules.issues.spreadsheet.NonExistingContainerError(
                            column="Container",
                            row=prop_no,
                            type="value_error.missing",
                            container_id=container_id,
                            msg="",
                            input=None,
                            url=None,
                        )
                    )
            for _container_no, container in enumerate(self.containers or []):
                for constraint_no, constraint in enumerate(container.constraint or []):
                    if constraint.as_id(self.metadata.space) not in defined_containers:
                        errors.append(
                            cognite.neat.rules.issues.spreadsheet.NonExistingContainerError(
                                column="Constraint",
                                row=constraint_no,
                                type="value_error.missing",
                                container_id=constraint.as_id(self.metadata.space),
                                msg="",
                                input=None,
                                url=None,
                            )
                        )
        if errors:
            raise issues.MultiValueError(errors)
        return self

    @model_validator(mode="after")
    def validate_schema(self) -> "DMSRules":
        if self.metadata.schema_ is not SchemaCompleteness.complete:
            return self

        schema = self.as_schema()
        errors = schema.validate()
        if errors:
            raise issues.MultiValueError(errors)
        return self

    @model_serializer(mode="plain", when_used="always")
    def dms_rules_serialization(self, info: SerializationInfo) -> dict[str, Any]:
        kwargs = vars(info)
        default_space = f"{self.metadata.space}:"
        default_version = f"version={self.metadata.default_view_version}"
        default_version_wrapped = f"({default_version})"
        properties = []
        field_names = (
            ["Class", "View", "Value Type", "Container"]
            if info.by_alias
            else ["class_", "view", "value_type", "container"]
        )
        value_type_name = "Value Type" if info.by_alias else "value_type"
        for prop in self.properties:
            dumped = prop.model_dump(**kwargs)
            for field_name in field_names:
                if value := dumped.get(field_name):
                    dumped[field_name] = value.removeprefix(default_space).removesuffix(default_version_wrapped)
            # Value type can have a property as well
            dumped[value_type_name] = dumped[value_type_name].replace(default_version, "")
            properties.append(dumped)

        views = []
        field_names = ["Class", "View", "Implements"] if info.by_alias else ["class_", "view", "implements"]
        implements_name = "Implements" if info.by_alias else "implements"
        for view in self.views:
            dumped = view.model_dump(**kwargs)
            for field_name in field_names:
                if value := dumped.get(field_name):
                    dumped[field_name] = value.removeprefix(default_space).removesuffix(default_version_wrapped)
            if value := dumped.get(implements_name):
                dumped[implements_name] = ",".join(
                    parent.strip().removeprefix(default_space).removesuffix(default_version_wrapped)
                    for parent in value.split(",")
                )
            views.append(dumped)

        containers = []
        field_names = ["Class", "Container"] if info.by_alias else ["class_", "container"]
        constraint_name = "Constraint" if info.by_alias else "constraint"
        for container in self.containers or []:
            dumped = container.model_dump(**kwargs)
            for field_name in field_names:
                if value := dumped.get(field_name):
                    dumped[field_name] = value.removeprefix(default_space).removesuffix(default_version_wrapped)
                if value := dumped.get(constraint_name):
                    dumped[constraint_name] = ",".join(
                        constraint.strip().removeprefix(default_space).removesuffix(default_version_wrapped)
                        for constraint in value.split(",")
                    )
            containers.append(dumped)

        return {
            "Metadata" if info.by_alias else "metadata": self.metadata.model_dump(**kwargs),
            "Properties" if info.by_alias else "properties": properties,
            "Views" if info.by_alias else "views": views,
            "Containers" if info.by_alias else "containers": containers,
        }

    def as_schema(
        self, standardize_casing: bool = True, include_pipeline: bool = False, instance_space: str | None = None
    ) -> DMSSchema:
        return _DMSExporter(standardize_casing, include_pipeline, instance_space).to_schema(self)

    def as_information_architect_rules(self) -> "InformationRules":
        return _DMSRulesConverter(self).as_information_architect_rules()

    def as_domain_expert_rules(self) -> DomainRules:
        return _DMSRulesConverter(self).as_domain_rules()


class _DMSExporter:
    """The DMS Exporter is responsible for exporting the DMSRules to a DMSSchema.

    This kept in this location such that it can be used by the DMSRules to validate the schema.
    (This module cannot have a dependency on the exporter module, as it would create a circular dependency.)

    Args
        standardize_casing (bool): If True, the casing of the identifiers will be standardized. This means external IDs
            are PascalCase and property names are camelCase.
        include_pipeline (bool): If True, the pipeline will be included with the schema. Pipeline means the
            raw tables and transformations necessary to populate the data model.
        instance_space (str): The space to use for the instance. Defaults to None,`Rules.metadata.space` will be used
    """

    def __init__(
        self, standardize_casing: bool = True, include_pipeline: bool = False, instance_space: str | None = None
    ):
        self.standardize_casing = standardize_casing
        self.include_pipeline = include_pipeline
        self.instance_space = instance_space

    def to_schema(self, rules: DMSRules) -> DMSSchema:
        default_version = "1"
        default_space = rules.metadata.space

        container_properties_by_id, view_properties_by_id = self._gather_properties(
            rules, default_space, default_version
        )

        containers = self._create_containers(rules.containers, container_properties_by_id, default_space)

        views, node_types = self._create_views_with_node_types(
            rules.views, view_properties_by_id, default_space, default_version
        )

        views_not_in_model = {
            view.view.as_id(default_space, default_version, self.standardize_casing)
            for view in rules.views
            if not view.in_model
        }
        data_model = rules.metadata.as_data_model()
        data_model.views = [view_id for view_id in views.as_ids() if view_id not in views_not_in_model]

        spaces = self._create_spaces(rules.metadata, containers, views, data_model)

        output = DMSSchema(
            spaces=spaces,
            data_models=dm.DataModelApplyList([data_model]),
            views=views,
            containers=containers,
            node_types=node_types,
        )
        if self.include_pipeline:
            return PipelineSchema.from_dms(output, self.instance_space)
        return output

    def _create_spaces(
        self,
        metadata: DMSMetadata,
        containers: dm.ContainerApplyList,
        views: dm.ViewApplyList,
        data_model: dm.DataModelApply,
    ) -> dm.SpaceApplyList:
        used_spaces = {container.space for container in containers} | {view.space for view in views}
        if len(used_spaces) == 1:
            # We skip the default space and only use this space for the data model
            data_model.space = used_spaces.pop()
            spaces = dm.SpaceApplyList([dm.SpaceApply(space=data_model.space)])
        else:
            spaces = dm.SpaceApplyList([metadata.as_space()] + [dm.SpaceApply(space=space) for space in used_spaces])
        if self.instance_space and self.instance_space not in {space.space for space in spaces}:
            spaces.append(dm.SpaceApply(space=self.instance_space, name=self.instance_space))
        return spaces

    def _create_views_with_node_types(
        self,
        dms_views: SheetList[DMSView],
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]],
        default_space: str,
        default_version: str,
    ) -> tuple[dm.ViewApplyList, dm.NodeApplyList]:
        views = dm.ViewApplyList(
            [dms_view.as_view(default_space, default_version, self.standardize_casing) for dms_view in dms_views]
        )
        for view in views:
            view_id = view.as_id()
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property: ViewPropertyApply
                if prop.is_list and prop.relation == "direct":
                    # This is not yet supported in the CDF API, a warning has already been issued, here we convert it to
                    # a multi-edge connection.
                    if isinstance(prop.value_type, ViewEntity):
                        source = prop.value_type.as_id(default_space, default_version, self.standardize_casing)
                    else:
                        raise ValueError(
                            "Direct relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    view_property = dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference(
                            space=source.space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        ),
                        source=source,
                        direction="outwards",
                    )
                elif prop.container and prop.container_property and prop.view_property:
                    container_prop_identifier = (
                        to_camel(prop.container_property) if self.standardize_casing else prop.container_property
                    )
                    extra_args: dict[str, Any] = {}
                    if prop.relation == "direct" and isinstance(prop.value_type, ViewEntity):
                        extra_args["source"] = prop.value_type.as_id(
                            default_space, default_version, self.standardize_casing
                        )
                    elif prop.relation == "direct" and not isinstance(prop.value_type, ViewEntity):
                        raise ValueError(
                            "Direct relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    view_property = dm.MappedPropertyApply(
                        container=prop.container.as_id(default_space, self.standardize_casing),
                        container_property_identifier=container_prop_identifier,
                        **extra_args,
                    )
                elif prop.view and prop.view_property and prop.relation == "multiedge":
                    if isinstance(prop.value_type, ViewEntity):
                        source = prop.value_type.as_id(default_space, default_version, self.standardize_casing)
                    else:
                        raise ValueError(
                            "Multiedge relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    view_property = dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference(
                            space=source.space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        ),
                        source=source,
                        direction="outwards",
                    )
                elif prop.view and prop.view_property and prop.relation == "reversedirect":
                    if isinstance(prop.value_type, ViewPropEntity):
                        source = prop.value_type.as_id(default_space, default_version, self.standardize_casing)
                    else:
                        raise ValueError(
                            "Reverse direct relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    source_prop = prop.value_type.property_
                    if source_prop is None:
                        raise ValueError(
                            "Reverse direct relation must set what it is the reverse property of. "
                            f"Which property in {prop.value_type.versioned_id} is this the reverse of? Expecting "
                            f"{prop.value_type.versioned_id}:<property>"
                        )
                    reverse_prop = next(
                        (prop for prop in view_properties_by_id.get(source, []) if prop.property_ == source_prop), None
                    )
                    if reverse_prop and reverse_prop.relation == "direct" and reverse_prop.is_list:
                        warnings.warn(
                            issues.dms.ReverseOfDirectRelationListWarning(view_id, prop.property_), stacklevel=2
                        )
                        view_property = dm.MultiEdgeConnectionApply(
                            type=dm.DirectRelationReference(
                                space=source.space,
                                external_id=f"{reverse_prop.view.external_id}.{reverse_prop.view_property}",
                            ),
                            source=source,
                            direction="inwards",
                        )
                    else:
                        args: dict[str, Any] = dict(
                            source=source,
                            through=dm.PropertyId(source, source_prop),
                            description=prop.description,
                            name=prop.name,
                        )
                        reverse_direct_cls: dict[
                            bool | None,
                            type[dm.MultiReverseDirectRelationApply] | type[SingleReverseDirectRelationApply],
                        ] = {
                            True: dm.MultiReverseDirectRelationApply,
                            False: SingleReverseDirectRelationApply,
                            None: dm.MultiReverseDirectRelationApply,
                        }

                        view_property = reverse_direct_cls[prop.is_list](**args)
                elif prop.view and prop.view_property and prop.relation:
                    warnings.warn(
                        issues.dms.UnsupportedRelationWarning(view_id, prop.view_property, prop.relation), stacklevel=2
                    )
                    continue
                else:
                    continue
                prop_name = to_camel(prop.view_property) if self.standardize_casing else prop.view_property
                view.properties[prop_name] = view_property

        node_types = dm.NodeApplyList([])
        parent_views = {parent for view in views for parent in view.implements or []}
        node_type_flag = False
        for view in views:
            ref_containers = view.referenced_containers()
            has_data = dm.filters.HasData(containers=list(ref_containers)) if ref_containers else None
            node_type = dm.filters.Equals(["node", "type"], {"space": view.space, "externalId": view.external_id})
            if view.as_id() in parent_views:
                view.filter = has_data
            elif has_data is None:
                # Child filter without container properties
                if node_type_flag:
                    # Transformations do not yet support setting node type.
                    view.filter = node_type
                    node_types.append(dm.NodeApply(space=view.space, external_id=view.external_id, sources=[]))
            else:
                # Child filter with its own container properties
                if node_type_flag:
                    # Transformations do not yet support setting node type.
                    view.filter = dm.filters.And(has_data, node_type)
                    node_types.append(dm.NodeApply(space=view.space, external_id=view.external_id, sources=[]))
                else:
                    view.filter = has_data
        return views, node_types

    def _create_containers(
        self,
        dms_container: SheetList[DMSContainer] | None,
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]],
        default_space: str,
    ) -> dm.ContainerApplyList:
        containers = dm.ContainerApplyList(
            [
                dms_container.as_container(default_space, self.standardize_casing)
                for dms_container in dms_container or []
            ]
        )
        container_to_drop = set()
        for container in containers:
            container_id = container.as_id()
            if not (container_properties := container_properties_by_id.get(container_id)):
                warnings.warn(issues.dms.EmptyContainerWarning(container_id=container_id), stacklevel=2)
                container_to_drop.add(container_id)
                continue
            for prop in container_properties:
                if prop.container_property is None:
                    continue
                if isinstance(prop.value_type, DMSValueType):
                    type_cls = prop.value_type.dms
                else:
                    type_cls = dm.DirectRelation

                prop_name = to_camel(prop.container_property) if self.standardize_casing else prop.container_property

                if type_cls is dm.DirectRelation:
                    container.properties[prop_name] = dm.ContainerProperty(
                        type=dm.DirectRelation(),
                        nullable=prop.nullable if prop.nullable is not None else True,
                        default_value=prop.default,
                        name=prop.name,
                        description=prop.description,
                    )
                else:
                    type_: CognitePropertyType
                    if issubclass(type_cls, ListablePropertyType):
                        type_ = type_cls(is_list=prop.is_list or False)
                    else:
                        type_ = cast(CognitePropertyType, type_cls())
                    container.properties[prop_name] = dm.ContainerProperty(
                        type=type_,
                        nullable=prop.nullable if prop.nullable is not None else True,
                        default_value=prop.default,
                        name=prop.name,
                        description=prop.description,
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

        # We might drop containers we convert direct relations of list into multi-edge connections
        # which do not have a container.
        for container in containers:
            if container.constraints:
                container.constraints = {
                    name: const
                    for name, const in container.constraints.items()
                    if not (isinstance(const, dm.RequiresConstraint) and const.require in container_to_drop)
                }
        return dm.ContainerApplyList(
            [container for container in containers if container.as_id() not in container_to_drop]
        )

    @classmethod
    def _gather_properties(
        cls, rules: DMSRules, default_space: str, default_version: str
    ) -> tuple[dict[dm.ContainerId, list[DMSProperty]], dict[dm.ViewId, list[DMSProperty]]]:
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in rules.properties:
            view_id = prop.view.as_id(default_space, default_version)
            view_properties_by_id[view_id].append(prop)

            if prop.container and prop.container_property:
                if prop.relation == "direct" and prop.is_list:
                    warnings.warn(
                        issues.dms.DirectRelationListWarning(
                            container_id=prop.container.as_id(default_space),
                            view_id=prop.view.as_id(default_space, default_version),
                            property=prop.container_property,
                        ),
                        stacklevel=2,
                    )
                    continue
                container_id = prop.container.as_id(default_space)
                container_properties_by_id[container_id].append(prop)

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
                # we do not want version in class as we use URI for the class
                class_=view.class_.as_non_versioned_entity(),
                description=view.description,
                parent=[
                    # we do not want version in class as we use URI for the class
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
                    class_=property_.class_.as_non_versioned_entity(),
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
