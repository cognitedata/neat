import warnings
from collections.abc import Hashable
from typing import Any, ClassVar, Literal

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import Field, field_serializer, field_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo

from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._constants import COGNITE_SPACES
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import (
    PrincipleMatchingSpaceAndVersionWarning,
)
from cognite.neat._rules.models._base_rules import (
    BaseMetadata,
    BaseRules,
    ContainerProperty,
    DataModelAspect,
    RoleTypes,
    SheetList,
    SheetRow,
    ViewProperty,
    ViewRef,
)
from cognite.neat._rules.models._types import (
    ClassEntityType,
    ContainerEntityType,
    DmsPropertyType,
    StrListType,
    URIRefType,
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

_DEFAULT_VERSION = "1"


class DMSMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms
    aspect: ClassVar[DataModelAspect] = DataModelAspect.physical
    logical: URIRefType | None = None

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
    view: ViewEntityType = Field(alias="View", description="The property identifier.")
    view_property: DmsPropertyType = Field(alias="View Property", description="The ViewId this property belongs to")
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the property")
    description: str | None = Field(alias="Description", default=None, description="Short description of the property")
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None = Field(
        None,
        alias="Connection",
        description="nly applies to connection between views. "
        "It specify how the connection should be implemented in CDF.",
    )
    value_type: DataType | ViewEntity | DMSUnknownEntity = Field(
        alias="Value Type",
        description="Value type that the property can hold. "
        "It takes either subset of CDF primitive types or a View id",
    )
    nullable: bool | None = Field(
        default=None,
        alias="Nullable",
        description="Used to indicate whether the property is required or not. Only applies to primitive type.",
    )
    immutable: bool | None = Field(
        default=None,
        alias="Immutable",
        description="sed to indicate whether the property is can only be set once. Only applies to primitive type.",
    )
    is_list: bool | None = Field(
        default=None,
        alias="Is List",
        description="Used to indicate whether the property holds single or multiple values (list). "
        "Only applies to primitive types.",
    )
    default: str | int | dict | None = Field(
        None, alias="Default", description="Specifies default value for the property."
    )
    container: ContainerEntityType | None = Field(
        None,
        alias="Container",
        description="Specifies container where the property is stored. Only applies to primitive type.",
    )
    container_property: DmsPropertyType | None = Field(
        None,
        alias="Container Property",
        description="Specifies property in the container where the property is stored. Only applies to primitive type.",
    )
    index: StrListType | None = Field(
        None,
        alias="Index",
        description="The names of the indexes (comma separated) that should be created for the property.",
    )
    constraint: StrListType | None = Field(
        None,
        alias="Constraint",
        description="The names of the uniquness (comma separated) that should be created for the property.",
    )
    logical: URIRefType | None = Field(
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

    def as_container_reference(self) -> ContainerProperty:
        if self.container is None or self.container_property is None:
            raise NeatValueError("Accessing container reference without container and container property set")
        return ContainerProperty(container=self.container, property_=self.container_property)

    def as_view_reference(self) -> ViewProperty:
        return ViewProperty(view=self.view, property_=self.view_property)


class DMSContainer(SheetRow):
    container: ContainerEntityType = Field(
        alias="Container", description="Container id, strongly advised to PascalCase usage."
    )
    name: str | None = Field(
        alias="Name", default=None, description="Human readable name of the container being defined."
    )
    description: str | None = Field(
        alias="Description", default=None, description="Short description of the node being defined."
    )
    constraint: ContainerEntityList | None = Field(
        None, alias="Constraint", description="List of required (comma separated) constraints for the container"
    )
    used_for: Literal["node", "edge", "all"] | None = Field(
        "all", alias="Used For", description=" Whether the container is used for nodes, edges or all."
    )

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
    view: ViewEntityType = Field(alias="View", description="View id, strongly advised to PascalCase usage.")
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the view being defined.")
    description: str | None = Field(
        alias="Description", default=None, description="Short description of the view being defined "
    )
    implements: ViewEntityList | None = Field(
        None,
        alias="Implements",
        description="List of parent view ids (comma separated) which the view being defined implements.",
    )
    filter_: HasDataFilter | NodeTypeFilter | RawFilter | None = Field(
        None, alias="Filter", description="Explicitly define the filter for the view."
    )
    in_model: bool = Field(
        True, alias="In Model", description="Indicates whether the view being defined is a part of the data model."
    )
    logical: URIRefType | None = Field(
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
            filter=None if self.filter_ is None else self.filter_.as_dms_filter(),
            implements=implements,
            properties={},
        )

    def as_view_reference(self) -> ViewRef:
        return ViewRef(view=self.view)


class DMSNode(SheetRow):
    node: DMSNodeEntity = Field(alias="Node", description="The type definition of the node.")
    usage: Literal["type", "collection"] = Field(
        alias="Usage", description="What the usage of the node is in the data model."
    )
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the node being defined.")
    description: str | None = Field(
        alias="Description", default=None, description="Short description of the node being defined."
    )

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
    collection: ClassEntityType = Field(alias="Collection", description="The collection this enum belongs to.")
    value: str = Field(alias="Value", description="The value of the enum.")
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the enum.")
    description: str | None = Field(alias="Description", default=None, description="Short description of the enum.")

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.collection, self.value

    @field_serializer("collection", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, DMSEntity) and (metadata := _metadata(info.context)):
            return value.dump(space=metadata.space, version=metadata.version)
        return str(value)


class DMSRules(BaseRules):
    metadata: DMSMetadata = Field(alias="Metadata", description="Contains information about the data model.")
    properties: SheetList[DMSProperty] = Field(
        alias="Properties", description="Contains the properties of the data model."
    )
    views: SheetList[DMSView] = Field(alias="Views", description="Contains the views of the data model.")
    containers: SheetList[DMSContainer] | None = Field(
        None,
        alias="Containers",
        description="Contains the definition containers that are the physical storage of the data model.",
    )
    enum: SheetList[DMSEnum] | None = Field(None, alias="Enum", description="Contains the definition of enum values.")
    nodes: SheetList[DMSNode] | None = Field(
        None, alias="Nodes", description="Contains the definition of the node types."
    )

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

    def as_schema(self, instance_space: str | None = None, remove_cdf_spaces: bool = False) -> DMSSchema:
        from ._exporter import _DMSExporter

        return _DMSExporter(self, instance_space, remove_cdf_spaces=remove_cdf_spaces).to_schema()

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
