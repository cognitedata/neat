import abc
import math
import re
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.views import SingleReverseDirectRelationApply, ViewPropertyApply
from pydantic import Field, field_serializer, field_validator, model_serializer, model_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo
from rdflib import Namespace

import cognite.neat.rules.issues.spreadsheet
from cognite.neat.rules import issues
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    ContainerEntityList,
    DMSUnknownEntity,
    ParentClassEntity,
    ReferenceEntity,
    Undefined,
    Unknown,
    URLEntity,
    ViewEntity,
    ViewEntityList,
    ViewPropertyEntity,
)
from cognite.neat.rules.models.rules._domain_rules import DomainRules

from ._base import BaseMetadata, BaseRules, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from ._dms_schema import DMSSchema, PipelineSchema
from ._types import (
    ExternalIdType,
    PropertyType,
    StrListType,
    VersionType,
)

if TYPE_CHECKING:
    from ._information_rules import InformationRules

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


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
    extension: ExtensionCategory = ExtensionCategory.addition
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
    def _get_description_and_creator(cls, description_raw: str | None) -> tuple[str | None, list[str]]:
        if description_raw and (description_match := re.search(r"Creator: (.+)", description_raw)):
            creator = description_match.group(1).split(", ")
            description = description_raw.replace(description_match.string, "").strip() or None
        elif description_raw:
            creator = ["MISSING"]
            description = description_raw
        else:
            creator = ["MISSING"]
            description = None
        return description, creator

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSMetadata":
        description, creator = cls._get_description_and_creator(data_model.description)
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
    value_type: DataType | ViewPropertyEntity | ViewEntity | DMSUnknownEntity = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None = Field(None, alias="Default")
    reference: URLEntity | ReferenceEntity | None = Field(default=None, alias="Reference", union_mode="left_to_right")
    container: ContainerEntity | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    view: ViewEntity = Field(alias="View")
    view_property: str = Field(alias="ViewProperty")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")

    @field_validator("nullable")
    def direct_relation_must_be_nullable(cls, value: Any, info: ValidationInfo) -> None:
        if info.data.get("relatVion") == "direct" and value is False:
            raise ValueError("Direct relation must be nullable")
        return value

    @field_validator("container_property", "container")
    def reverse_direct_relation_has_no_container(cls, value, info: ValidationInfo) -> None:
        if info.data.get("relation") == "reversedirect" and value is not None:
            raise ValueError(f"Reverse direct relation must not have container or container property, got {value}")
        return value

    @field_validator("value_type", mode="after")
    def relations_value_type(cls, value: DataType | ClassEntity, info: ValidationInfo) -> DataType | ClassEntity:
        if (relation := info.data["relation"]) is None:
            return value
        if not isinstance(value, ViewEntity | ViewPropertyEntity | DMSUnknownEntity):
            raise ValueError(f"Relations must have a value type that points to another view, got {value}")
        if relation == "reversedirect" and value.property_ is None:
            # Todo fix this error message. It have the wrong syntax for how to have a property
            raise ValueError(
                "Reverse direct relation must set what it is the reverse property of. "
                f"Which property in {value.versioned_id} is this the reverse of? Expecting"
                f"{value.versioned_id}:<property>"
            )
        return value

    @field_serializer("value_type", when_used="always")
    @staticmethod
    def as_dms_type(value_type: DataType | ViewPropertyEntity | ViewEntity) -> str:
        if isinstance(value_type, DataType):
            return value_type.dms._type
        else:
            return str(value_type)


class DMSContainer(SheetEntity):
    container: ContainerEntity = Field(alias="Container")
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    constraint: ContainerEntityList | None = Field(None, alias="Constraint")

    def as_container(self) -> dm.ContainerApply:
        container_id = self.container.as_id()
        constraints: dict[str, dm.Constraint] = {}
        for constraint in self.constraint or []:
            requires = dm.RequiresConstraint(constraint.as_id())
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
            container=ContainerEntity(space=container.space, externalId=container.external_id),
            name=container.name or None,
            description=container.description,
            constraint=constraints or None,
        )


class DMSView(SheetEntity):
    view: ViewEntity = Field(alias="View")
    implements: ViewEntityList | None = Field(None, alias="Implements")
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    filter_: Literal["hasData", "nodeType"] | None = Field(None, alias="Filter")
    in_model: bool = Field(True, alias="InModel")

    def as_view(self) -> dm.ViewApply:
        view_id = self.view.as_id()
        return dm.ViewApply(
            space=view_id.space,
            external_id=view_id.external_id,
            version=view_id.version,
            name=self.name or None,
            description=self.description,
            implements=[parent.as_id() for parent in self.implements or []] or None,
            properties={},
        )

    @classmethod
    def from_view(cls, view: dm.ViewApply, data_model_view_ids: set[dm.ViewId]) -> "DMSView":
        return cls(
            class_=ClassEntity(prefix=view.space, suffix=view.external_id),
            view=ViewEntity(space=view.space, externalId=view.external_id, version=view.version),
            description=view.description,
            name=view.name,
            implements=[
                ViewEntity(space=parent.space, externalId=parent.external_id, version=parent.version)
                for parent in view.implements
            ]
            or None,
            in_model=view.as_id() in data_model_view_ids,
        )


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    views: SheetList[DMSView] = Field(alias="Views")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    reference: "DMSRules | None" = Field(None, alias="Reference")

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
            container_id = container.as_id()
            row_numbers = {prop_no for prop_no, _ in properties}
            value_types = {prop.value_type for _, prop in properties if prop.value_type}
            if len(value_types) > 1:
                errors.append(
                    cognite.neat.rules.issues.spreadsheet.MultiValueTypeError(
                        container_id, prop_name, row_numbers, {v.dms._type for v in value_types}
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
        defined_views = {view.view.as_id() for view in self.views}

        errors: list[issues.NeatValidationError] = []
        for prop_no, prop in enumerate(self.properties):
            if prop.view and (view_id := prop.view.as_id()) not in defined_views:
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
            defined_containers = {container.container.as_id() for container in self.containers or []}
            for prop_no, prop in enumerate(self.properties):
                if prop.container and (container_id := prop.container.as_id()) not in defined_containers:
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
                    if constraint.as_id() not in defined_containers:
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
    def validate_extension(self) -> "DMSRules":
        if self.metadata.schema_ is not SchemaCompleteness.extended:
            return self
        if not self.reference:
            raise ValueError("The schema is set to 'extended', but no reference rules are provided to validate against")
        is_solution = self.metadata.space != self.reference.metadata.space
        if is_solution:
            return self
        if self.metadata.extension is ExtensionCategory.rebuild:
            # Everything is allowed
            return self
        # Is an extension of an existing model.
        user_schema = self.as_schema()
        ref_schema = self.reference.as_schema()
        new_containers = {container.as_id(): container for container in user_schema.containers}
        existing_containers = {container.as_id(): container for container in ref_schema.containers}

        errors: list[issues.NeatValidationError] = []
        for container_id, container in new_containers.items():
            existing_container = existing_containers.get(container_id)
            if not existing_container or existing_container == container:
                # No problem
                continue
            new_dumped = container.dump()
            existing_dumped = existing_container.dump()
            changed_attributes, changed_properties = self._changed_attributes_and_properties(
                new_dumped, existing_dumped
            )
            errors.append(
                issues.dms.ChangingContainerError(
                    container_id=container_id,
                    changed_properties=changed_properties or None,
                    changed_attributes=changed_attributes or None,
                )
            )

        if self.metadata.extension is ExtensionCategory.reshape and errors:
            raise issues.MultiValueError(errors)
        elif self.metadata.extension is ExtensionCategory.reshape:
            # Reshape allows changes to views
            return self

        new_views = {view.as_id(): view for view in user_schema.views}
        existing_views = {view.as_id(): view for view in ref_schema.views}
        for view_id, view in new_views.items():
            existing_view = existing_views.get(view_id)
            if not existing_view or existing_view == view:
                # No problem
                continue
            changed_attributes, changed_properties = self._changed_attributes_and_properties(
                view.dump(), existing_view.dump()
            )
            errors.append(
                issues.dms.ChangingViewError(
                    view_id=view_id,
                    changed_properties=changed_properties or None,
                    changed_attributes=changed_attributes or None,
                )
            )

        if errors:
            raise issues.MultiValueError(errors)
        return self

    @staticmethod
    def _changed_attributes_and_properties(
        new_dumped: dict[str, Any], existing_dumped: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Helper method to find the changed attributes and properties between two containers or views."""
        new_attributes = {key: value for key, value in new_dumped.items() if key != "properties"}
        existing_attributes = {key: value for key, value in existing_dumped.items() if key != "properties"}
        changed_attributes = [key for key in new_attributes if new_attributes[key] != existing_attributes.get(key)]
        new_properties = new_dumped.get("properties", {})
        existing_properties = existing_dumped.get("properties", {})
        changed_properties = [prop for prop in new_properties if new_properties[prop] != existing_properties.get(prop)]
        return changed_attributes, changed_properties

    @model_validator(mode="after")
    def validate_schema(self) -> "DMSRules":
        if self.metadata.schema_ is SchemaCompleteness.partial:
            return self
        elif self.metadata.schema_ is SchemaCompleteness.complete:
            rules: DMSRules = self
        elif self.metadata.schema_ is SchemaCompleteness.extended:
            if not self.reference:
                raise ValueError(
                    "The schema is set to 'extended', but no reference rules are provided to validate against"
                )
            # This is an extension of the reference rules, we need to merge the two
            rules = self.model_copy(deep=True)
            rules.properties.extend(self.reference.properties.data)
            existing_views = {view.view.as_id() for view in rules.views}
            rules.views.extend([view for view in self.reference.views if view.view.as_id() not in existing_views])
            if rules.containers and self.reference.containers:
                existing_containers = {container.container.as_id() for container in rules.containers.data}
                rules.containers.extend(
                    [
                        container
                        for container in self.reference.containers
                        if container.container.as_id() not in existing_containers
                    ]
                )
            elif not rules.containers and self.reference.containers:
                rules.containers = self.reference.containers
        else:
            raise ValueError("Unknown schema completeness")

        schema = rules.as_schema()
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

        output = {
            "Metadata" if info.by_alias else "metadata": self.metadata.model_dump(**kwargs),
            "Properties" if info.by_alias else "properties": properties,
            "Views" if info.by_alias else "views": views,
            "Containers" if info.by_alias else "containers": containers,
        }
        if self.reference is not None:
            output["Reference" if info.by_alias else "reference"] = self.reference.model_dump(**kwargs)
        return output

    def as_schema(self, include_pipeline: bool = False, instance_space: str | None = None) -> DMSSchema:
        return _DMSExporter(include_pipeline, instance_space).to_schema(self)

    def as_information_architect_rules(self) -> "InformationRules":
        return _DMSRulesConverter(self).as_information_architect_rules()

    def as_domain_expert_rules(self) -> DomainRules:
        return _DMSRulesConverter(self).as_domain_rules()

    def reference_self(self) -> Self:
        new_rules = self.model_copy(deep=True)
        for prop in new_rules.properties:
            prop.reference = ReferenceEntity(
                prefix=prop.view.prefix, suffix=prop.view.suffix, version=prop.view.version, property_=prop.property_
            )
        view: DMSView
        for view in new_rules.views:
            view.reference = ReferenceEntity(
                prefix=view.view.prefix, suffix=view.view.suffix, version=view.view.version
            )
        container: DMSContainer
        for container in new_rules.containers or []:
            container.reference = ReferenceEntity(prefix=container.container.prefix, suffix=container.container.suffix)
        return new_rules


class _DMSExporter:
    """The DMS Exporter is responsible for exporting the DMSRules to a DMSSchema.

    This kept in this location such that it can be used by the DMSRules to validate the schema.
    (This module cannot have a dependency on the exporter module, as it would create a circular dependency.)

    Args
        include_pipeline (bool): If True, the pipeline will be included with the schema. Pipeline means the
            raw tables and transformations necessary to populate the data model.
        instance_space (str): The space to use for the instance. Defaults to None,`Rules.metadata.space` will be used
    """

    def __init__(self, include_pipeline: bool = False, instance_space: str | None = None):
        self.include_pipeline = include_pipeline
        self.instance_space = instance_space

    def to_schema(self, rules: DMSRules) -> DMSSchema:
        container_properties_by_id, view_properties_by_id = self._gather_properties(rules)

        containers = self._create_containers(rules.containers, container_properties_by_id)

        views, node_types = self._create_views_with_node_types(rules.views, view_properties_by_id)

        views_not_in_model = {view.view.as_id() for view in rules.views if not view.in_model}
        data_model = rules.metadata.as_data_model()
        data_model.views = sorted(
            [view_id for view_id in views.as_ids() if view_id not in views_not_in_model], key=lambda v: v.as_tuple()  # type: ignore[union-attr]
        )

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
            used_spaces.add(metadata.space)
            spaces = dm.SpaceApplyList([dm.SpaceApply(space=space) for space in used_spaces])
        if self.instance_space and self.instance_space not in {space.space for space in spaces}:
            spaces.append(dm.SpaceApply(space=self.instance_space, name=self.instance_space))
        return spaces

    def _create_views_with_node_types(
        self,
        dms_views: SheetList[DMSView],
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]],
    ) -> tuple[dm.ViewApplyList, dm.NodeApplyList]:
        views = dm.ViewApplyList([dms_view.as_view() for dms_view in dms_views])
        dms_view_by_id = {dms_view.view.as_id(): dms_view for dms_view in dms_views}

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
                        source_view_id = prop.value_type.as_id()
                    elif isinstance(prop.value_type, ViewPropertyEntity):
                        source_view_id = prop.value_type.as_id().source
                    else:
                        raise ValueError(
                            "Direct relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    view_property = dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference(
                            space=source_view_id.space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        ),
                        source=source_view_id,
                        direction="outwards",
                        name=prop.name,
                        description=prop.description,
                    )
                elif prop.container and prop.container_property and prop.view_property:
                    container_prop_identifier = prop.container_property
                    extra_args: dict[str, Any] = {}
                    if prop.relation == "direct" and isinstance(prop.value_type, ViewEntity):
                        extra_args["source"] = prop.value_type.as_id()
                    elif isinstance(prop.value_type, DMSUnknownEntity):
                        extra_args["source"] = None
                    elif prop.relation == "direct" and not isinstance(prop.value_type, ViewEntity):
                        raise ValueError(
                            "Direct relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    view_property = dm.MappedPropertyApply(
                        container=prop.container.as_id(),
                        container_property_identifier=container_prop_identifier,
                        name=prop.name,
                        description=prop.description,
                        **extra_args,
                    )
                elif prop.view and prop.view_property and prop.relation == "multiedge":
                    if isinstance(prop.value_type, ViewEntity):
                        source_view_id = prop.value_type.as_id()
                    else:
                        raise ValueError(
                            "Multiedge relation must have a view as value type. "
                            "This should have been validated in the rules"
                        )
                    if isinstance(prop.reference, ReferenceEntity):
                        ref_view_prop = prop.reference.as_view_property_id()
                        edge_type = dm.DirectRelationReference(
                            space=ref_view_prop.source.space,
                            external_id=f"{ref_view_prop.source.external_id}.{ref_view_prop.property}",
                        )
                    else:
                        edge_type = dm.DirectRelationReference(
                            space=source_view_id.space,
                            external_id=f"{prop.view.external_id}.{prop.view_property}",
                        )

                    view_property = dm.MultiEdgeConnectionApply(
                        type=edge_type,
                        source=source_view_id,
                        direction="outwards",
                        name=prop.name,
                        description=prop.description,
                    )
                elif prop.view and prop.view_property and prop.relation == "reversedirect":
                    if isinstance(prop.value_type, ViewPropertyEntity):
                        source_prop_id = prop.value_type.as_id()
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
                        (
                            prop
                            for prop in view_properties_by_id.get(source_prop_id.source, [])
                            if prop.property_ == source_prop
                        ),
                        None,
                    )
                    if reverse_prop and reverse_prop.relation == "direct" and reverse_prop.is_list:
                        warnings.warn(
                            issues.dms.ReverseOfDirectRelationListWarning(view_id, prop.property_), stacklevel=2
                        )
                        if isinstance(reverse_prop.reference, ReferenceEntity):
                            ref_view_prop = reverse_prop.reference.as_view_property_id()
                            edge_type = dm.DirectRelationReference(
                                space=ref_view_prop.source.space,
                                external_id=f"{ref_view_prop.source.external_id}.{ref_view_prop.property}",
                            )
                        else:
                            edge_type = dm.DirectRelationReference(
                                space=source_prop_id.source.space,
                                external_id=f"{reverse_prop.view.external_id}.{reverse_prop.view_property}",
                            )
                        view_property = dm.MultiEdgeConnectionApply(
                            type=edge_type,
                            source=source_prop_id.source,
                            direction="inwards",
                            name=prop.name,
                            description=prop.description,
                        )
                    else:
                        args: dict[str, Any] = dict(
                            source=source_prop_id.source,
                            through=dm.PropertyId(source_prop_id.source, source_prop),
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
                prop_id = prop.view_property
                view.properties[prop_id] = view_property

        node_types = dm.NodeApplyList([])
        parent_views = {parent for view in views for parent in view.implements or []}
        for view in views:
            ref_containers = sorted(view.referenced_containers(), key=lambda c: c.as_tuple())
            dms_view = dms_view_by_id.get(view.as_id())
            has_data = dm.filters.HasData(containers=list(ref_containers)) if ref_containers else None
            if dms_view and isinstance(dms_view.reference, ReferenceEntity):
                # If the view is a reference, we implement the reference view,
                # and need the filter to match the reference
                ref_view = dms_view.reference.as_view_id()
                node_type = dm.filters.Equals(
                    ["node", "type"], {"space": ref_view.space, "externalId": ref_view.external_id}
                )
            else:
                node_type = dm.filters.Equals(["node", "type"], {"space": view.space, "externalId": view.external_id})
            if view.as_id() in parent_views:
                if dms_view and dms_view.filter_ == "nodeType":
                    warnings.warn(issues.dms.NodeTypeFilterOnParentViewWarning(view.as_id()), stacklevel=2)
                    view.filter = node_type
                    node_types.append(dm.NodeApply(space=view.space, external_id=view.external_id, sources=[]))
                else:
                    view.filter = has_data
            elif has_data is None:
                # Child filter without container properties
                if dms_view and dms_view.filter_ == "hasData":
                    warnings.warn(issues.dms.HasDataFilterOnNoPropertiesViewWarning(view.as_id()), stacklevel=2)
                view.filter = node_type
                node_types.append(dm.NodeApply(space=view.space, external_id=view.external_id, sources=[]))
            else:
                if dms_view and (dms_view.filter_ == "hasData" or dms_view.filter_ is None):
                    # Default option
                    view.filter = has_data
                elif dms_view and dms_view.filter_ == "nodeType":
                    view.filter = node_type
                    node_types.append(dm.NodeApply(space=view.space, external_id=view.external_id, sources=[]))
                else:
                    view.filter = has_data
        return views, node_types

    def _create_containers(
        self,
        dms_container: SheetList[DMSContainer] | None,
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]],
    ) -> dm.ContainerApplyList:
        containers = dm.ContainerApplyList([dms_container.as_container() for dms_container in dms_container or []])
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
                if isinstance(prop.value_type, DataType):
                    type_cls = prop.value_type.dms
                else:
                    type_cls = dm.DirectRelation

                prop_id = prop.container_property

                if type_cls is dm.DirectRelation:
                    container.properties[prop_id] = dm.ContainerProperty(
                        type=dm.DirectRelation(),
                        nullable=prop.nullable if prop.nullable is not None else True,
                        default_value=prop.default,
                        name=prop.name,
                        description=prop.description,
                    )
                else:
                    type_: CognitePropertyType
                    type_ = type_cls(is_list=prop.is_list or False)
                    container.properties[prop_id] = dm.ContainerProperty(
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

    def _gather_properties(
        self, rules: DMSRules
    ) -> tuple[dict[dm.ContainerId, list[DMSProperty]], dict[dm.ViewId, list[DMSProperty]]]:
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in rules.properties:
            view_id = prop.view.as_id()
            view_properties_by_id[view_id].append(prop)

            if prop.container and prop.container_property:
                if prop.relation == "direct" and prop.is_list:
                    warnings.warn(
                        issues.dms.DirectRelationListWarning(
                            container_id=prop.container.as_id(),
                            view_id=prop.view.as_id(),
                            property=prop.container_property,
                        ),
                        stacklevel=2,
                    )
                    continue
                container_id = prop.container.as_id()
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
        from ._information_rules import InformationClass, InformationMetadata, InformationProperty, InformationRules

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

        classes = [
            InformationClass(
                # we do not want a version in class as we use URI for the class
                class_=view.class_.as_non_versioned_entity(),
                description=view.description,
                parent=[
                    # we do not want a version in class as we use URI for the class
                    ParentClassEntity(prefix=implemented_view.prefix, suffix=implemented_view.suffix)
                    # We only want parents in the same namespace, parent in a different namespace is a reference
                    for implemented_view in view.implements or []
                    if implemented_view.prefix == view.class_.prefix
                ],
                reference=self._get_class_reference(view),
            )
            for view in self.dms.views
        ]

        properties: list[InformationProperty] = []
        value_type: DataType | ClassEntity | str
        for property_ in self.dms.properties:
            if isinstance(property_.value_type, DataType):
                value_type = property_.value_type
            elif isinstance(property_.value_type, ViewEntity | ViewPropertyEntity):
                value_type = ClassEntity(
                    prefix=property_.value_type.prefix,
                    suffix=property_.value_type.suffix,
                )
            elif isinstance(property_.value_type, DMSUnknownEntity):
                value_type = ClassEntity(
                    prefix=Undefined,
                    suffix=Unknown,
                )
            else:
                raise ValueError(f"Unsupported value type: {property_.value_type.type_}")

            properties.append(
                InformationProperty(
                    class_=property_.class_.as_non_versioned_entity(),
                    property_=property_.view_property,
                    value_type=value_type,
                    description=property_.description,
                    min_count=0 if property_.nullable or property_.nullable is None else 1,
                    max_count=float("inf") if property_.is_list or property_.nullable is None else 1,
                    reference=self._get_property_reference(property_),
                )
            )

        return InformationRules(
            metadata=metadata,
            properties=SheetList[InformationProperty](data=properties),
            classes=SheetList[InformationClass](data=classes),
            reference=self.dms.reference and self.dms.reference.as_information_architect_rules(),  # type: ignore[arg-type]
        )

    @classmethod
    def _get_class_reference(cls, view: DMSView) -> ReferenceEntity | None:
        parents_other_namespace = [parent for parent in view.implements or [] if parent.prefix != view.class_.prefix]
        if len(parents_other_namespace) == 0:
            return None
        if len(parents_other_namespace) > 1:
            warnings.warn(
                issues.dms.MultipleReferenceWarning(
                    view_id=view.view.as_id(), implements=[v.as_id() for v in parents_other_namespace]
                ),
                stacklevel=2,
            )
        other_parent = parents_other_namespace[0]

        return ReferenceEntity(prefix=other_parent.prefix, suffix=other_parent.suffix)

    @classmethod
    def _get_property_reference(cls, property_: DMSProperty) -> ReferenceEntity | None:
        has_container_other_namespace = property_.container and property_.container.prefix != property_.class_.prefix
        if not has_container_other_namespace:
            return None
        container = cast(ContainerEntity, property_.container)
        return ReferenceEntity(
            prefix=container.prefix,
            suffix=container.suffix,
            property=property_.container_property,
        )
