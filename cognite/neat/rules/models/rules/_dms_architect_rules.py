import abc
import math
import re
import sys
import warnings
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import PropertyType as CognitePropertyType
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.views import (
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)
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
    DMSNodeEntity,
    DMSUnknownEntity,
    ParentClassEntity,
    ReferenceEntity,
    UnknownEntity,
    URLEntity,
    ViewEntity,
    ViewEntityList,
    ViewPropertyEntity,
)
from cognite.neat.rules.models.rules._domain_rules import DomainRules
from cognite.neat.rules.models.wrapped_entities import DMSFilter, HasDataFilter, NodeTypeFilter

from ._base import (
    BaseMetadata,
    BaseRules,
    DataModelType,
    ExtensionCategory,
    RoleTypes,
    SchemaCompleteness,
    SheetEntity,
    SheetList,
)
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

_DEFAULT_VERSION = "1"

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
    data_model_type: DataModelType = Field(DataModelType.solution, alias="dataModelType")
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

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_serializer("schema_", "extension", "data_model_type", when_used="always")
    @staticmethod
    def as_string(value: SchemaCompleteness | ExtensionCategory | DataModelType) -> str:
        return str(value)

    @field_validator("schema_", mode="plain")
    def as_enum_schema(cls, value: str) -> SchemaCompleteness:
        return SchemaCompleteness(value)

    @field_validator("extension", mode="plain")
    def as_enum_extension(cls, value: str) -> ExtensionCategory:
        return ExtensionCategory(value)

    @field_validator("data_model_type", mode="plain")
    def as_enum_model_type(cls, value: str) -> DataModelType:
        return DataModelType(value)

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
    view: ViewEntity = Field(alias="View")
    view_property: str = Field(alias="ViewProperty")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    relation: Literal["direct", "edge", "reverse"] | None = Field(None, alias="Relation")
    value_type: DataType | ViewPropertyEntity | ViewEntity | DMSUnknownEntity = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    is_list: bool | None = Field(default=None, alias="IsList")
    default: str | int | dict | None = Field(None, alias="Default")
    reference: URLEntity | ReferenceEntity | None = Field(default=None, alias="Reference", union_mode="left_to_right")
    container: ContainerEntity | None = Field(None, alias="Container")
    container_property: str | None = Field(None, alias="ContainerProperty")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")
    class_: ClassEntity = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")

    @field_validator("nullable")
    def direct_relation_must_be_nullable(cls, value: Any, info: ValidationInfo) -> None:
        if info.data.get("relation") == "direct" and value is False:
            raise ValueError("Direct relation must be nullable")
        return value

    @field_validator("value_type", mode="after")
    def relations_value_type(
        cls, value: ViewPropertyEntity | ViewEntity | DMSUnknownEntity, info: ValidationInfo
    ) -> DataType | ViewPropertyEntity | ViewEntity | DMSUnknownEntity:
        if (relation := info.data.get("relation")) is None:
            return value
        if relation == "direct" and not isinstance(value, ViewEntity | DMSUnknownEntity):
            raise ValueError(f"Direct relation must have a value type that points to a view, got {value}")
        elif relation == "edge" and not isinstance(value, ViewEntity):
            raise ValueError(f"Edge relation must have a value type that points to a view, got {value}")
        elif relation == "reverse" and not isinstance(value, ViewPropertyEntity | ViewEntity):
            raise ValueError(
                f"Reverse relation must have a value type that points to a view or view property, got {value}"
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
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    constraint: ContainerEntityList | None = Field(None, alias="Constraint")
    class_: ClassEntity = Field(alias="Class")

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
        container_entity = ContainerEntity.from_id(container.as_id())
        return cls(
            class_=container_entity.as_class(),
            container=container_entity,
            name=container.name or None,
            description=container.description,
            constraint=constraints or None,
        )


class DMSView(SheetEntity):
    view: ViewEntity = Field(alias="View")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    implements: ViewEntityList | None = Field(None, alias="Implements")
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    filter_: HasDataFilter | NodeTypeFilter | None = Field(None, alias="Filter")
    in_model: bool = Field(True, alias="InModel")
    class_: ClassEntity = Field(alias="Class")

    def as_view(self) -> dm.ViewApply:
        view_id = self.view.as_id()
        return dm.ViewApply(
            space=view_id.space,
            external_id=view_id.external_id,
            version=view_id.version or _DEFAULT_VERSION,
            name=self.name or None,
            description=self.description,
            implements=[parent.as_id() for parent in self.implements or []] or None,
            properties={},
        )

    @classmethod
    def from_view(cls, view: dm.ViewApply, in_model: bool) -> "DMSView":
        view_entity = ViewEntity.from_id(view.as_id())
        class_entity = view_entity.as_class(skip_version=True)

        return cls(
            class_=class_entity,
            view=view_entity,
            description=view.description,
            name=view.name,
            implements=[ViewEntity.from_id(parent, _DEFAULT_VERSION) for parent in view.implements] or None,
            in_model=in_model,
        )


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    views: SheetList[DMSView] = Field(alias="Views")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    reference: "DMSRules | None" = Field(None, alias="Reference")

    @field_validator("reference")
    def check_reference_of_reference(cls, value: "DMSRules | None") -> "DMSRules | None":
        if value is None:
            return None
        if value.reference is not None:
            raise ValueError("Reference rules cannot have a reference")
        return value

    @field_validator("views")
    def matching_version(cls, value: SheetList[DMSView], info: ValidationInfo) -> SheetList[DMSView]:
        if not (metadata := info.data.get("metadata")):
            return value
        model_version = metadata.version
        if different_version := [view.view.as_id() for view in value if view.view.version != model_version]:
            warnings.warn(issues.dms.ViewModelVersionNotMatchingWarning(different_version, model_version), stacklevel=2)
        return value

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
                        container_id,
                        prop_name,
                        row_numbers,
                        {v.dms._type if isinstance(v, DataType) else str(v) for v in value_types},
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
                                container_id=constraint.as_id(),
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
        user_schema = self.as_schema(include_ref=False)
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

    @model_serializer(mode="wrap", when_used="always")
    def dms_rules_serialization(
        self,
        handler: Callable,
        info: SerializationInfo,
    ) -> dict[str, Any]:
        dumped = cast(dict[str, Any], handler(self, info))
        space, version = self.metadata.space, self.metadata.version
        return _DMSRulesSerializer(info, space, version).clean(dumped)

    def as_schema(
        self, include_ref: bool = False, include_pipeline: bool = False, instance_space: str | None = None
    ) -> DMSSchema:
        return _DMSExporter(self, include_ref, include_pipeline, instance_space).to_schema()

    def as_information_architect_rules(self) -> "InformationRules":
        return _DMSRulesConverter(self).as_information_architect_rules()

    def as_domain_expert_rules(self) -> DomainRules:
        return _DMSRulesConverter(self).as_domain_rules()

    def reference_self(self) -> Self:
        new_rules = self.model_copy(deep=True)
        for prop in new_rules.properties:
            prop.reference = ReferenceEntity(
                prefix=prop.view.prefix, suffix=prop.view.suffix, version=prop.view.version, property=prop.property_
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

    def __init__(
        self,
        rules: DMSRules,
        include_ref: bool = True,
        include_pipeline: bool = False,
        instance_space: str | None = None,
    ):
        self.include_ref = include_ref
        self.include_pipeline = include_pipeline
        self.instance_space = instance_space
        self.rules = rules
        self._ref_schema = rules.reference.as_schema() if rules.reference else None
        if self._ref_schema:
            # We skip version as that will always be missing in the reference
            self._ref_views_by_id = {dm.ViewId(view.space, view.external_id): view for view in self._ref_schema.views}
        else:
            self._ref_views_by_id = {}

    def to_schema(self) -> DMSSchema:
        rules = self.rules
        container_properties_by_id, view_properties_by_id = self._gather_properties()
        containers = self._create_containers(container_properties_by_id)

        views, node_types = self._create_views_with_node_types(view_properties_by_id)

        views_not_in_model = {view.view.as_id() for view in rules.views if not view.in_model}
        data_model = rules.metadata.as_data_model()
        data_model.views = sorted(
            [view_id for view_id in views.as_ids() if view_id not in views_not_in_model],
            key=lambda v: v.as_tuple(),  # type: ignore[union-attr]
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

        if self._ref_schema and self.include_ref:
            output.frozen_ids.update(self._ref_schema.node_types.as_ids())
            output.frozen_ids.update(self._ref_schema.views.as_ids())
            output.frozen_ids.update(self._ref_schema.containers.as_ids())
            output.node_types.extend(self._ref_schema.node_types)
            output.views.extend(self._ref_schema.views)
            output.containers.extend(self._ref_schema.containers)
            output.data_models.extend(self._ref_schema.data_models)

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
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]],
    ) -> tuple[dm.ViewApplyList, dm.NodeApplyList]:
        views = dm.ViewApplyList([dms_view.as_view() for dms_view in self.rules.views])
        dms_view_by_id = {dms_view.view.as_id(): dms_view for dms_view in self.rules.views}

        for view in views:
            view_id = view.as_id()
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property = self._create_view_property(prop, view_properties_by_id)
                if view_property is not None:
                    view.properties[prop.view_property] = view_property

        data_model_type = self.rules.metadata.data_model_type
        unique_node_types: set[dm.NodeId] = set()
        parent_views = {parent for view in views for parent in view.implements or []}
        for view in views:
            dms_view = dms_view_by_id.get(view.as_id())
            dms_properties = view_properties_by_id.get(view.as_id(), [])
            view_filter = self._create_view_filter(view, dms_view, data_model_type, dms_properties)

            view.filter = view_filter.as_dms_filter()

            if isinstance(view_filter, NodeTypeFilter):
                unique_node_types.update(view_filter.nodes)
                if view.as_id() in parent_views:
                    warnings.warn(issues.dms.NodeTypeFilterOnParentViewWarning(view.as_id()), stacklevel=2)
            elif isinstance(view_filter, HasDataFilter) and data_model_type == DataModelType.solution:
                if dms_view and isinstance(dms_view.reference, ReferenceEntity):
                    references = {dms_view.reference.as_view_id()}
                elif any(True for prop in dms_properties if isinstance(prop.reference, ReferenceEntity)):
                    references = {
                        prop.reference.as_view_id()
                        for prop in dms_properties
                        if isinstance(prop.reference, ReferenceEntity)
                    }
                else:
                    continue
                warnings.warn(
                    issues.dms.HasDataFilterOnViewWithReferencesWarning(view.as_id(), list(references)), stacklevel=2
                )

        return views, dm.NodeApplyList(
            [dm.NodeApply(space=node.space, external_id=node.external_id) for node in unique_node_types]
        )

    @classmethod
    def _create_edge_type_from_prop(cls, prop: DMSProperty) -> dm.DirectRelationReference:
        if isinstance(prop.reference, ReferenceEntity):
            ref_view_prop = prop.reference.as_view_property_id()
            return cls._create_edge_type_from_view_id(cast(dm.ViewId, ref_view_prop.source), ref_view_prop.property)
        else:
            return cls._create_edge_type_from_view_id(prop.view.as_id(), prop.view_property)

    @staticmethod
    def _create_edge_type_from_view_id(view_id: dm.ViewId, property_: str) -> dm.DirectRelationReference:
        return dm.DirectRelationReference(
            space=view_id.space,
            # This is the same convention as used when converting GraphQL to DMS
            external_id=f"{view_id.external_id}.{property_}",
        )

    def _create_containers(
        self,
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]],
    ) -> dm.ContainerApplyList:
        containers = dm.ContainerApplyList(
            [dms_container.as_container() for dms_container in self.rules.containers or []]
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
                if isinstance(prop.value_type, DataType):
                    type_cls = prop.value_type.dms
                else:
                    type_cls = dm.DirectRelation

                type_ = type_cls(is_list=prop.is_list or False)
                container.properties[prop.container_property] = dm.ContainerProperty(
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

    def _gather_properties(self) -> tuple[dict[dm.ContainerId, list[DMSProperty]], dict[dm.ViewId, list[DMSProperty]]]:
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in self.rules.properties:
            view_id = prop.view.as_id()
            view_properties_by_id[view_id].append(prop)

            if prop.container and prop.container_property:
                container_id = prop.container.as_id()
                container_properties_by_id[container_id].append(prop)

        return container_properties_by_id, view_properties_by_id

    def _create_view_filter(
        self,
        view: dm.ViewApply,
        dms_view: DMSView | None,
        data_model_type: DataModelType,
        dms_properties: list[DMSProperty],
    ) -> DMSFilter:
        selected_filter_name = (dms_view and dms_view.filter_ and dms_view.filter_.name) or ""
        if dms_view and dms_view.filter_ and not dms_view.filter_.is_empty:
            # Has Explicit Filter, use it
            return dms_view.filter_

        if data_model_type == DataModelType.solution and selected_filter_name in [NodeTypeFilter.name, ""]:
            if (
                dms_view
                and isinstance(dms_view.reference, ReferenceEntity)
                and not dms_properties
                and (ref_view := self._ref_views_by_id.get(dms_view.reference.as_view_id()))
                and ref_view.filter
            ):
                # No new properties, only reference, reuse the reference filter
                return DMSFilter.from_dms_filter(ref_view.filter)
            else:
                referenced_node_ids = {
                    prop.reference.as_node_entity()
                    for prop in dms_properties
                    if isinstance(prop.reference, ReferenceEntity)
                }
                if dms_view and isinstance(dms_view.reference, ReferenceEntity):
                    referenced_node_ids.add(dms_view.reference.as_node_entity())
                if referenced_node_ids:
                    return NodeTypeFilter(inner=list(referenced_node_ids))

        # Enterprise Model or (Solution + HasData)
        ref_containers = view.referenced_containers()
        if not ref_containers or selected_filter_name == HasDataFilter.name:
            # Child filter without container properties
            if selected_filter_name == HasDataFilter.name:
                warnings.warn(issues.dms.HasDataFilterOnNoPropertiesViewWarning(view.as_id()), stacklevel=2)
            return NodeTypeFilter(inner=[DMSNodeEntity(space=view.space, externalId=view.external_id)])
        else:
            # HasData or not provided (this is the default)
            return HasDataFilter(inner=[ContainerEntity.from_id(id_) for id_ in ref_containers])

    def _create_view_property(
        self, prop: DMSProperty, view_properties_by_id: dict[dm.ViewId, list[DMSProperty]]
    ) -> ViewPropertyApply | None:
        if prop.container and prop.container_property:
            container_prop_identifier = prop.container_property
            extra_args: dict[str, Any] = {}
            if prop.relation == "direct":
                if isinstance(prop.value_type, ViewEntity):
                    extra_args["source"] = prop.value_type.as_id()
                elif isinstance(prop.value_type, DMSUnknownEntity):
                    extra_args["source"] = None
                else:
                    # Should have been validated.
                    raise ValueError(
                        "If this error occurs it is a bug in NEAT, please report"
                        f"Debug Info, Invalid valueType direct: {prop.model_dump_json()}"
                    )
            elif prop.relation is not None:
                # Should have been validated.
                raise ValueError(
                    "If this error occurs it is a bug in NEAT, please report"
                    f"Debug Info, Invalid relation: {prop.model_dump_json()}"
                )
            return dm.MappedPropertyApply(
                container=prop.container.as_id(),
                container_property_identifier=container_prop_identifier,
                name=prop.name,
                description=prop.description,
                **extra_args,
            )
        elif prop.relation == "edge":
            if isinstance(prop.value_type, ViewEntity):
                source_view_id = prop.value_type.as_id()
            else:
                # Should have been validated.
                raise ValueError(
                    "If this error occurs it is a bug in NEAT, please report"
                    f"Debug Info, Invalid valueType edge: {prop.model_dump_json()}"
                )
            edge_cls: type[dm.EdgeConnectionApply] = dm.MultiEdgeConnectionApply
            # If is_list is not set, we default to a MultiEdgeConnection
            if prop.is_list is False:
                edge_cls = SingleEdgeConnectionApply

            return edge_cls(
                type=self._create_edge_type_from_prop(prop),
                source=source_view_id,
                direction="outwards",
                name=prop.name,
                description=prop.description,
            )
        elif prop.relation == "reverse":
            reverse_prop_id: str | None = None
            if isinstance(prop.value_type, ViewPropertyEntity):
                source_view_id = prop.value_type.as_view_id()
                reverse_prop_id = prop.value_type.property_
            elif isinstance(prop.value_type, ViewEntity):
                source_view_id = prop.value_type.as_id()
            else:
                # Should have been validated.
                raise ValueError(
                    "If this error occurs it is a bug in NEAT, please report"
                    f"Debug Info, Invalid valueType reverse relation: {prop.model_dump_json()}"
                )
            reverse_prop: DMSProperty | None = None
            if reverse_prop_id is not None:
                reverse_prop = next(
                    (
                        prop
                        for prop in view_properties_by_id.get(source_view_id, [])
                        if prop.property_ == reverse_prop_id
                    ),
                    None,
                )

            if reverse_prop is None:
                warnings.warn(
                    issues.dms.ReverseRelationMissingOtherSideWarning(source_view_id, prop.view_property),
                    stacklevel=2,
                )

            if reverse_prop is None or reverse_prop.relation == "edge":
                inwards_edge_cls = (
                    dm.MultiEdgeConnectionApply if prop.is_list in [True, None] else SingleEdgeConnectionApply
                )
                return inwards_edge_cls(
                    type=self._create_edge_type_from_prop(reverse_prop or prop),
                    source=source_view_id,
                    name=prop.name,
                    description=prop.description,
                    direction="inwards",
                )
            elif reverse_prop_id and reverse_prop and reverse_prop.relation == "direct":
                reverse_direct_cls = (
                    dm.MultiReverseDirectRelationApply if prop.is_list is True else SingleReverseDirectRelationApply
                )
                return reverse_direct_cls(
                    source=source_view_id,
                    through=dm.PropertyId(source=source_view_id, property=reverse_prop_id),
                    name=prop.name,
                    description=prop.description,
                )
            else:
                return None

        elif prop.view and prop.view_property and prop.relation:
            warnings.warn(
                issues.dms.UnsupportedRelationWarning(prop.view.as_id(), prop.view_property, prop.relation or ""),
                stacklevel=2,
            )
        return None


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
                class_=ClassEntity(prefix=view.class_.prefix, suffix=view.class_.suffix),
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
                value_type = UnknownEntity()
            else:
                raise ValueError(f"Unsupported value type: {property_.value_type.type_}")

            properties.append(
                InformationProperty(
                    # Removing version
                    class_=ClassEntity(suffix=property_.class_.suffix, prefix=property_.class_.prefix),
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


class _DMSRulesSerializer:
    # These are the fields that need to be cleaned from the default space and version
    PROPERTIES_FIELDS: ClassVar[list[str]] = ["class_", "view", "value_type", "container"]
    VIEWS_FIELDS: ClassVar[list[str]] = ["class_", "view", "implements"]
    CONTAINERS_FIELDS: ClassVar[list[str]] = ["class_", "container"]

    def __init__(self, info: SerializationInfo, default_space: str, default_version: str) -> None:
        self.default_space = f"{default_space}:"
        self.default_version = f"version={default_version}"
        self.default_version_wrapped = f"({self.default_version})"

        self.properties_fields = self.PROPERTIES_FIELDS
        self.views_fields = self.VIEWS_FIELDS
        self.containers_fields = self.CONTAINERS_FIELDS
        self.prop_name = "properties"
        self.view_name = "views"
        self.container_name = "containers"
        self.metadata_name = "metadata"
        self.prop_view = "view"
        self.prop_view_property = "view_property"
        self.prop_value_type = "value_type"
        self.view_view = "view"
        self.view_implements = "implements"
        self.container_container = "container"
        self.container_constraint = "constraint"

        if info.by_alias:
            self.properties_fields = [
                DMSProperty.model_fields[field].alias or field for field in self.properties_fields
            ]
            self.views_fields = [DMSView.model_fields[field].alias or field for field in self.views_fields]
            self.container_fields = [
                DMSContainer.model_fields[field].alias or field for field in self.containers_fields
            ]
            self.prop_view = DMSProperty.model_fields[self.prop_view].alias or self.prop_view
            self.prop_view_property = DMSProperty.model_fields[self.prop_view_property].alias or self.prop_view_property
            self.prop_value_type = DMSProperty.model_fields[self.prop_value_type].alias or self.prop_value_type
            self.view_view = DMSView.model_fields[self.view_view].alias or self.view_view
            self.view_implements = DMSView.model_fields[self.view_implements].alias or self.view_implements
            self.container_container = (
                DMSContainer.model_fields[self.container_container].alias or self.container_container
            )
            self.container_constraint = (
                DMSContainer.model_fields[self.container_constraint].alias or self.container_constraint
            )
            self.prop_name = DMSRules.model_fields[self.prop_name].alias or self.prop_name
            self.view_name = DMSRules.model_fields[self.view_name].alias or self.view_name
            self.container_name = DMSRules.model_fields[self.container_name].alias or self.container_name
            self.metadata_name = DMSRules.model_fields[self.metadata_name].alias or self.metadata_name

        if isinstance(info.exclude, dict):
            # Just for happy mypy
            exclude = cast(dict, info.exclude)
            self.exclude_properties = exclude.get("properties", {}).get("__all__", set())
            self.exclude_views = exclude.get("views", {}).get("__all__", set()) or set()
            self.exclude_containers = exclude.get("containers", {}).get("__all__", set()) or set()
            self.metadata_exclude = exclude.get("metadata", set()) or set()
            self.exclude_top = {k for k, v in exclude.items() if not v}
        else:
            self.exclude_top = set(info.exclude or {})
            self.exclude_properties = set()
            self.exclude_views = set()
            self.exclude_containers = set()
            self.metadata_exclude = set()

    def clean(self, dumped: dict[str, Any]) -> dict[str, Any]:
        # Sorting to get a deterministic order
        dumped[self.prop_name] = sorted(
            dumped[self.prop_name]["data"], key=lambda p: (p[self.prop_view], p[self.prop_view_property])
        )
        dumped[self.view_name] = sorted(dumped[self.view_name]["data"], key=lambda v: v[self.view_view])
        if self.container_name in dumped:
            dumped[self.container_name] = sorted(
                dumped[self.container_name]["data"], key=lambda c: c[self.container_container]
            )

        for prop in dumped[self.prop_name]:
            for field_name in self.properties_fields:
                if value := prop.get(field_name):
                    prop[field_name] = value.removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
            # Value type can have a property as well
            prop[self.prop_value_type] = prop[self.prop_value_type].replace(self.default_version, "")
            if self.exclude_properties:
                for field in self.exclude_properties:
                    prop.pop(field, None)

        for view in dumped[self.view_name]:
            for field_name in self.views_fields:
                if value := view.get(field_name):
                    view[field_name] = value.removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
            if value := view.get(self.view_implements):
                view[self.view_implements] = ",".join(
                    parent.strip().removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
                    for parent in value.split(",")
                )
            if self.exclude_views:
                for field in self.exclude_views:
                    view.pop(field, None)

        for container in dumped[self.container_name]:
            for field_name in self.containers_fields:
                if value := container.get(field_name):
                    container[field_name] = value.removeprefix(self.default_space)

            if value := container.get(self.container_constraint):
                container[self.container_constraint] = ",".join(
                    constraint.strip().removeprefix(self.default_space) for constraint in value.split(",")
                )
            if self.exclude_containers:
                for field in self.exclude_containers:
                    container.pop(field, None)

        if self.metadata_exclude:
            for field in self.metadata_exclude:
                dumped[self.metadata_name].pop(field, None)
        for field in self.exclude_top:
            dumped.pop(field, None)
        return dumped
