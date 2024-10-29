import math
import sys
import warnings
from collections.abc import Hashable
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo

from cognite.neat._issues import MultiValueError
from cognite.neat._issues.warnings import (
    PrincipleMatchingSpaceAndVersionWarning,
    PrincipleSolutionBuildsOnEnterpriseWarning,
)
from cognite.neat._rules.models._base_rules import (
    BaseMetadata,
    BaseRules,
    DataModelType,
    ExtensionCategory,
    RoleTypes,
    SchemaCompleteness,
    SheetList,
    SheetRow,
)
from cognite.neat._rules.models._types import (
    ClassEntityType,
    ContainerEntityType,
    DataModelExternalIdType,
    DmsPropertyType,
    InformationPropertyType,
    SpaceType,
    StrListType,
    VersionType,
    ViewEntityType,
)
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ContainerEntityList,
    DMSEntity,
    DMSNodeEntity,
    DMSUnknownEntity,
    EdgeEntity,
    Entity,
    HasDataFilter,
    NodeTypeFilter,
    RawFilter,
    ReferenceEntity,
    ReverseConnectionEntity,
    URLEntity,
    ViewEntity,
    ViewEntityList,
)

from ._schema import DMSSchema

if TYPE_CHECKING:
    pass

if sys.version_info >= (3, 11):
    pass
else:
    pass

_DEFAULT_VERSION = "1"


class DMSMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms
    data_model_type: DataModelType = Field(DataModelType.enterprise, alias="dataModelType")
    schema_: SchemaCompleteness = Field(alias="schema")
    extension: ExtensionCategory = ExtensionCategory.addition
    space: SpaceType
    name: str | None = Field(
        None,
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(None, min_length=1, max_length=1024)
    external_id: DataModelExternalIdType = Field(alias="externalId")
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
    def as_string(self, value: SchemaCompleteness | ExtensionCategory | DataModelType) -> str:
        return str(value)

    @field_validator("schema_", mode="plain")
    def as_enum_schema(cls, value: str) -> SchemaCompleteness:
        return SchemaCompleteness(value.strip())

    @field_validator("extension", mode="plain")
    def as_enum_extension(cls, value: str) -> ExtensionCategory:
        return ExtensionCategory(value.strip())

    @field_validator("data_model_type", mode="plain")
    def as_enum_model_type(cls, value: str) -> DataModelType:
        return DataModelType(value.strip())

    @field_validator("description", mode="before")
    def nan_as_none(cls, value):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    def as_space(self) -> dm.SpaceApply:
        return dm.SpaceApply(
            space=self.space,
        )

    def as_data_model_id(self) -> dm.DataModelId:
        return dm.DataModelId(space=self.space, external_id=self.external_id, version=self.version)

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

    def as_identifier(self) -> str:
        return repr(self.as_data_model_id())

    def get_prefix(self) -> str:
        return self.space


def _metadata(context: Any) -> DMSMetadata | None:
    if isinstance(context, dict) and isinstance(context.get("metadata"), DMSMetadata):
        return context["metadata"]
    return None


class DMSProperty(SheetRow):
    view: ViewEntityType = Field(alias="View")
    view_property: DmsPropertyType = Field(alias="View Property")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None = Field(None, alias="Connection")
    value_type: DataType | ViewEntity | DMSUnknownEntity = Field(alias="Value Type")
    nullable: bool | None = Field(default=None, alias="Nullable")
    immutable: bool | None = Field(default=None, alias="Immutable")
    is_list: bool | None = Field(default=None, alias="Is List")
    default: str | int | dict | None = Field(None, alias="Default")
    reference: URLEntity | ReferenceEntity | None = Field(default=None, alias="Reference", union_mode="left_to_right")
    container: ContainerEntityType | None = Field(None, alias="Container")
    container_property: DmsPropertyType | None = Field(None, alias="Container Property")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")
    class_: ClassEntityType = Field(alias="Class (linage)")
    property_: InformationPropertyType = Field(alias="Property (linage)")

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.view, self.view_property

    @field_validator("nullable")
    def direct_relation_must_be_nullable(cls, value: Any, info: ValidationInfo) -> None:
        if info.data.get("connection") == "direct" and value is False:
            raise ValueError("Direct relation must be nullable")
        return value

    @field_validator("value_type", mode="after")
    def connections_value_type(
        cls, value: EdgeEntity | ViewEntity | DMSUnknownEntity, info: ValidationInfo
    ) -> DataType | EdgeEntity | ViewEntity | DMSUnknownEntity:
        if (connection := info.data.get("connection")) is None:
            return value
        if connection == "direct" and not isinstance(value, ViewEntity | DMSUnknownEntity):
            raise ValueError(f"Direct relation must have a value type that points to a view, got {value}")
        elif isinstance(connection, EdgeEntity) and not isinstance(value, ViewEntity):
            raise ValueError(f"Edge connection must have a value type that points to a view, got {value}")
        elif isinstance(connection, ReverseConnectionEntity) and not isinstance(value, ViewEntity):
            raise ValueError(f"Reverse connection must have a value type that points to a view, got {value}")
        return value

    @field_serializer("reference", when_used="always")
    def set_reference(self, value: Any, info: SerializationInfo) -> str | None:
        if isinstance(info.context, dict) and info.context.get("as_reference") is True:
            return str(
                ReferenceEntity(
                    prefix=self.view.prefix,
                    suffix=self.view.suffix,
                    version=self.view.version,
                    property=self.view_property,
                )
            )
        return str(value) if value is not None else None

    @field_serializer("value_type", when_used="always")
    def as_dms_type(self, value_type: DataType | EdgeEntity | ViewEntity, info: SerializationInfo) -> str:
        if isinstance(value_type, DataType):
            return value_type._suffix_extra_args(value_type.dms._type)
        elif isinstance(value_type, EdgeEntity | ViewEntity) and (metadata := _metadata(info.context)):
            return value_type.dump(space=metadata.space, version=metadata.version)
        return str(value_type)

    @field_serializer("view", "container", "class_", when_used="unless-none")
    def remove_default_space(self, value: str, info: SerializationInfo) -> str:
        if (metadata := _metadata(info.context)) and isinstance(value, Entity):
            if info.field_name == "container" and info.context.get("as_reference") is True:
                # When dumping as reference, the container should keep the default space for easy copying
                # over to user sheets.
                return value.dump()
            return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("connection", when_used="unless-none")
    def remove_defaults(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, Entity) and (metadata := _metadata(info.context)):
            default_type = f"{metadata.space}{self.view.external_id}.{self.view_property}"
            return value.dump(space=metadata.space, version=metadata.version, type=default_type)
        return str(value)


class DMSContainer(SheetRow):
    container: ContainerEntityType = Field(alias="Container")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    constraint: ContainerEntityList | None = Field(None, alias="Constraint")
    used_for: Literal["node", "edge", "all"] | None = Field("all", alias="Used For")
    class_: ClassEntityType = Field(alias="Class (linage)")

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.container,)

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
            used_for=self.used_for,
        )

    @field_serializer("reference", when_used="always")
    def set_reference(self, value: Any, info: SerializationInfo) -> str | None:
        if isinstance(info.context, dict) and info.context.get("as_reference") is True:
            return self.container.dump()
        return str(value) if value is not None else None

    @field_serializer("container", "class_", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if metadata := _metadata(info.context):
            if isinstance(value, DMSEntity):
                return value.dump(space=metadata.space, version=metadata.version)
            elif isinstance(value, Entity):
                return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("constraint", when_used="unless-none")
    def remove_default_spaces(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _metadata(info.context)):
            return ",".join(
                constraint.dump(space=metadata.space, version=metadata.version)
                if isinstance(constraint, DMSEntity)
                else str(constraint)
                for constraint in value
            )
        return ",".join(str(value) for value in value)


class DMSView(SheetRow):
    view: ViewEntityType = Field(alias="View")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    implements: ViewEntityList | None = Field(None, alias="Implements")
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    filter_: HasDataFilter | NodeTypeFilter | RawFilter | None = Field(None, alias="Filter")
    in_model: bool = Field(True, alias="In Model")
    class_: ClassEntityType = Field(alias="Class (linage)")

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.view,)

    @field_serializer("reference", when_used="always")
    def set_reference(self, value: Any, info: SerializationInfo) -> str | None:
        if isinstance(info.context, dict) and info.context.get("as_reference") is True:
            return self.view.dump()
        return str(value) if value is not None else None

    @field_serializer("view", "class_", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _metadata(info.context)) and isinstance(value, Entity):
            return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("implements", when_used="unless-none")
    def remove_default_spaces(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _metadata(info.context)):
            return ",".join(
                parent.dump(space=metadata.space, version=metadata.version)
                if isinstance(parent, DMSEntity)
                else str(parent)
                for parent in value
            )
        return ",".join(str(value) for value in value) if isinstance(value, list) else value

    def as_view(self) -> dm.ViewApply:
        view_id = self.view.as_id()
        implements = [parent.as_id() for parent in self.implements or []] or None
        if implements is None and isinstance(self.reference, ReferenceEntity):
            # Fallback to the reference if no implements are provided
            parent = self.reference.as_view_id()
            if (parent.space, parent.external_id) != (view_id.space, view_id.external_id):
                implements = [parent]

        return dm.ViewApply(
            space=view_id.space,
            external_id=view_id.external_id,
            version=view_id.version or _DEFAULT_VERSION,
            name=self.name or None,
            description=self.description,
            implements=implements,
            properties={},
        )


class DMSNode(SheetRow):
    node: DMSNodeEntity = Field(alias="Node")
    usage: Literal["type", "collection"] = Field(alias="Usage")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.node,)

    def as_node(self) -> dm.NodeApply:
        if self.usage == "type":
            return dm.NodeApply(space=self.node.space, external_id=self.node.external_id)
        elif self.usage == "collection":
            raise NotImplementedError("Collection nodes are not supported yet")
        else:
            raise ValueError(f"Unknown usage {self.usage}")

    @field_serializer("node", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, DMSEntity) and (metadata := _metadata(info.context)):
            return value.dump(space=metadata.space, version=metadata.version)
        return str(value)


class DMSEnum(SheetRow):
    collection: ClassEntityType = Field(alias="Collection")
    value: str = Field(alias="Value")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.collection, self.value

    @field_serializer("collection", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, DMSEntity) and (metadata := _metadata(info.context)):
            return value.dump(space=metadata.space, version=metadata.version)
        return str(value)


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata")
    properties: SheetList[DMSProperty] = Field(alias="Properties")
    views: SheetList[DMSView] = Field(alias="Views")
    containers: SheetList[DMSContainer] | None = Field(None, alias="Containers")
    enum: SheetList[DMSEnum] | None = Field(None, alias="Enum")
    nodes: SheetList[DMSNode] | None = Field(None, alias="Nodes")
    last: "DMSRules | None" = Field(None, alias="Last", description="The previous version of the data model")
    reference: "DMSRules | None" = Field(None, alias="Reference")

    @field_validator("reference")
    def check_reference_of_reference(cls, value: "DMSRules | None", info: ValidationInfo) -> "DMSRules | None":
        if value is None:
            return None
        if value.reference is not None:
            raise ValueError("Reference rules cannot have a reference")
        if value.metadata.data_model_type == DataModelType.solution and (metadata := info.data.get("metadata")):
            warnings.warn(
                PrincipleSolutionBuildsOnEnterpriseWarning(
                    f"The solution model {metadata.as_data_model_id()} is referencing another "
                    f"solution model {value.metadata.as_data_model_id()}",
                ),
                stacklevel=2,
            )
        return value

    @field_validator("views")
    def matching_version_and_space(cls, value: SheetList[DMSView], info: ValidationInfo) -> SheetList[DMSView]:
        if not (metadata := info.data.get("metadata")):
            return value
        model_version = metadata.version
        if different_version := [view.view.as_id() for view in value if view.view.version != model_version]:
            for view_id in different_version:
                warnings.warn(
                    PrincipleMatchingSpaceAndVersionWarning(
                        f"The view {view_id!r} has a different version than the data model version, {model_version}",
                    ),
                    stacklevel=2,
                )
        if different_space := [view.view.as_id() for view in value if view.view.space != metadata.space]:
            for view_id in different_space:
                warnings.warn(
                    PrincipleMatchingSpaceAndVersionWarning(
                        f"The view {view_id!r} is in a different space than the data model space, {metadata.space}",
                    ),
                    stacklevel=2,
                )
        return value

    @model_validator(mode="after")
    def post_validation(self) -> "DMSRules":
        from ._validation import DMSPostValidation

        issue_list = DMSPostValidation(self).validate()
        if issue_list.warnings:
            issue_list.trigger_warnings()
        if issue_list.has_errors:
            raise MultiValueError(issue_list.errors)
        return self

    def as_schema(self, include_pipeline: bool = False, instance_space: str | None = None) -> DMSSchema:
        from ._exporter import _DMSExporter

        return _DMSExporter(self, include_pipeline, instance_space).to_schema()

    def _repr_html_(self) -> str:
        summary = {
            "type": "Physical Data Model",
            "intended for": "DMS Architect",
            "name": self.metadata.name,
            "space": self.metadata.space,
            "external_id": self.metadata.external_id,
            "version": self.metadata.version,
            "views": len(self.views),
            "containers": len(self.containers) if self.containers else 0,
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
