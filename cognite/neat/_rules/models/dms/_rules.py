import warnings
from collections.abc import Hashable
from typing import Any, ClassVar, Literal

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo
from rdflib import URIRef

from cognite.neat._constants import COGNITE_SPACES
from cognite.neat._issues import MultiValueError
from cognite.neat._issues.warnings import (
    PrincipleMatchingSpaceAndVersionWarning,
)
from cognite.neat._rules.models._base_rules import (
    BaseMetadata,
    BaseRules,
    DataModelAspect,
    RoleTypes,
    SheetList,
    SheetRow,
)
from cognite.neat._rules.models._types import (
    ClassEntityType,
    ContainerEntityType,
    DmsPropertyType,
    StrListType,
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
    ReverseConnectionEntity,
    ViewEntity,
    ViewEntityList,
)

from ._schema import DMSSchema

_DEFAULT_VERSION = "1"


class DMSMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms
    aspect: ClassVar[DataModelAspect] = DataModelAspect.physical
    logical: str | None = None

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
    container: ContainerEntityType | None = Field(None, alias="Container")
    container_property: DmsPropertyType | None = Field(None, alias="Container Property")
    index: StrListType | None = Field(None, alias="Index")
    constraint: StrListType | None = Field(None, alias="Constraint")
    logical: URIRef | None = Field(
        None,
        alias="Logical",
        description="Used to make connection between physical and logical data model aspect",
    )

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

    @field_validator("container", "container_property", mode="after")
    def container_set_correctly(cls, value: Any, info: ValidationInfo) -> Any:
        if (connection := info.data.get("connection")) is None:
            return value
        if connection == "direct" and value is None:
            raise ValueError(
                "You must provide a container and container property for where to store direct connections"
            )
        elif isinstance(connection, EdgeEntity) and value is not None:
            raise ValueError(
                "Edge connections are not stored in a container, please remove the container and container property"
            )
        elif isinstance(connection, ReverseConnectionEntity) and value is not None:
            raise ValueError(
                "Reverse connection are not stored in a container, please remove the container and container property"
            )
        return value

    @field_serializer("value_type", when_used="always")
    def as_dms_type(self, value_type: DataType | EdgeEntity | ViewEntity, info: SerializationInfo) -> str:
        if isinstance(value_type, DataType):
            return value_type._suffix_extra_args(value_type.dms._type)
        elif isinstance(value_type, EdgeEntity | ViewEntity) and (metadata := _metadata(info.context)):
            return value_type.dump(space=metadata.space, version=metadata.version)
        return str(value_type)

    @field_serializer("view", "container", when_used="unless-none")
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
            default_type = f"{self.view.external_id}.{self.view_property}"
            if isinstance(value, EdgeEntity) and value.edge_type and value.edge_type.space != metadata.space:
                default_type = f"{metadata.space}{default_type}"
            return value.dump(space=metadata.space, version=metadata.version, type=default_type)
        return str(value)


class DMSContainer(SheetRow):
    container: ContainerEntityType = Field(alias="Container")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    constraint: ContainerEntityList | None = Field(None, alias="Constraint")
    used_for: Literal["node", "edge", "all"] | None = Field("all", alias="Used For")

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

    @field_serializer("container", when_used="unless-none")
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
    filter_: HasDataFilter | NodeTypeFilter | RawFilter | None = Field(None, alias="Filter")
    in_model: bool = Field(True, alias="In Model")
    logical: URIRef | None = Field(
        None,
        alias="Logical",
        description="Used to make connection between physical and logical data model aspect",
    )

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.view,)

    @field_serializer("view", when_used="unless-none")
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

    @field_validator("views")
    def matching_version_and_space(cls, value: SheetList[DMSView], info: ValidationInfo) -> SheetList[DMSView]:
        if not (metadata := info.data.get("metadata")):
            return value
        model_version = metadata.version
        if different_version := [
            view.view.as_id()
            for view in value
            if view.view.version != model_version and view.view.space not in COGNITE_SPACES
        ]:
            for view_id in different_version:
                warnings.warn(
                    PrincipleMatchingSpaceAndVersionWarning(
                        f"The view {view_id!r} has a different version than the data model version, {model_version}",
                    ),
                    stacklevel=2,
                )
        if different_space := [
            view.view.as_id()
            for view in value
            if view.view.space != metadata.space and view.view.space not in COGNITE_SPACES
        ]:
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
            "aspect": self.metadata.aspect,
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
