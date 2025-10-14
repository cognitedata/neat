import math
import warnings
from collections.abc import Hashable
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo, ValidationInfo

from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._constants import DMS_CONTAINER_LIST_MAX_LIMIT
from cognite.neat.v0.core._data_model._constants import CONSTRAINT_ID_MAX_LENGTH
from cognite.neat.v0.core._data_model.models._base_verified import (
    BaseVerifiedDataModel,
    BaseVerifiedMetadata,
    ContainerProperty,
    DataModelLevel,
    RoleTypes,
    SheetList,
    SheetRow,
    ViewProperty,
    ViewRef,
)
from cognite.neat.v0.core._data_model.models._types import (
    ConceptEntityType,
    ContainerEntityType,
    PhysicalPropertyType,
    URIRefType,
    ViewEntityType,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptualEntity,
    ContainerIndexEntity,
    DMSNodeEntity,
    EdgeEntity,
    HasDataFilter,
    NodeTypeFilter,
    PhysicalEntity,
    PhysicalUnknownEntity,
    RawFilter,
    ReverseConnectionEntity,
    Undefined,
    ViewEntity,
    ViewEntityList,
)
from cognite.neat.v0.core._data_model.models.entities._types import (
    ContainerConstraintListType,
    ContainerIndexListType,
)
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.warnings import NeatValueWarning, PropertyDefinitionWarning

if TYPE_CHECKING:
    from cognite.neat.v0.core._data_model.models import ConceptualDataModel

_DEFAULT_VERSION = "1"


class PhysicalMetadata(BaseVerifiedMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.dms
    level: ClassVar[DataModelLevel] = DataModelLevel.physical
    conceptual: URIRefType | None = None

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

    def get_prefix(self) -> str:
        return self.space


def _metadata(context: Any) -> PhysicalMetadata | None:
    if isinstance(context, dict) and isinstance(context.get("metadata"), PhysicalMetadata):
        return context["metadata"]
    return None


class PhysicalProperty(SheetRow):
    """Physical property provides a complete definition of a property in the data model in a physical data model.
    This includes view to which the property belongs as well mapping between the view and container property.
    """

    view: ViewEntityType = Field(alias="View", description="The property identifier.")
    view_property: PhysicalPropertyType = Field(
        alias="View Property", description="The ViewId this property belongs to"
    )
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the property")
    description: str | None = Field(alias="Description", default=None, description="Short description of the property")
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None = Field(
        None,
        alias="Connection",
        description="nly applies to connection between views. "
        "It specify how the connection should be implemented in CDF.",
    )
    value_type: DataType | ViewEntity | PhysicalUnknownEntity = Field(
        alias="Value Type",
        description="Value type that the property can hold. It takes either subset of CDF primitive types or a View id",
    )
    min_count: int | None = Field(
        alias="Min Count",
        default=None,
        description="Minimum number of values that the property can hold. "
        "If no value is provided, the default value is  `0`, "
        "which means that the property is optional.",
    )
    max_count: int | float | None = Field(
        alias="Max Count",
        default=None,
        description="Maximum number of values that the property can hold. "
        "If no value is provided, the default value is  `inf`, "
        "which means that the property can hold any number of values (listable).",
    )
    immutable: bool | None = Field(
        default=None,
        alias="Immutable",
        description="sed to indicate whether the property is can only be set once. Only applies to primitive type.",
    )
    default: bool | str | int | float | dict | None = Field(
        None, alias="Default", description="Specifies default value for the property."
    )
    container: ContainerEntityType | None = Field(
        None,
        alias="Container",
        description="Specifies container where the property is stored. Only applies to primitive type.",
    )
    container_property: PhysicalPropertyType | None = Field(
        None,
        alias="Container Property",
        description="Specifies property in the container where the property is stored. Only applies to primitive type.",
    )
    index: ContainerIndexListType | None = Field(
        None,
        alias="Index",
        description="The names of the indexes (comma separated) that should be created for the property.",
    )
    constraint: ContainerConstraintListType | None = Field(
        None,
        alias="Constraint",
        description="The names of the uniquness (comma separated) that should be created for the property.",
    )
    conceptual: URIRefType | None = Field(
        None,
        alias="Conceptual",
        description="Used to make connection between physical and conceptual data model aspect",
    )

    @property
    def nullable(self) -> bool | None:
        """Used to indicate whether the property is required or not. Only applies to primitive type."""
        return self.min_count in {0, None}

    @property
    def is_list(self) -> bool | None:
        """Used to indicate whether the property holds single or multiple values (list). "
        "Only applies to primitive types."""
        if self.max_count is None:
            return None
        return self.max_count is float("inf") or (isinstance(self.max_count, int | float) and self.max_count > 1)

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.view, self.view_property

    @field_validator("min_count")
    def direct_relation_must_be_nullable(cls, value: Any, info: ValidationInfo) -> None:
        if info.data.get("connection") == "direct" and value not in {0, None}:
            raise ValueError("Direct relation must have min count set to 0")
        return value

    @field_validator("max_count", mode="before")
    def as_integer(cls, value: Any) -> Any:
        if isinstance(value, float) and not math.isinf(value):
            return int(value)
        return value

    @field_validator("max_count")
    def max_list_size(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(info.data.get("connection"), EdgeEntity | ReverseConnectionEntity):
            if value is not None and value != float("inf") and not (isinstance(value, int) and value == 1):
                raise ValueError("Edge and reverse connections must have max count set to inf or 1")
            return value
        # We do not have a connection, so we can check the max list size.
        if isinstance(value, int) and value > DMS_CONTAINER_LIST_MAX_LIMIT:
            raise ValueError(f"Max list size cannot be greater than {DMS_CONTAINER_LIST_MAX_LIMIT}")
        return value

    @field_validator("value_type", mode="after")
    def connections_value_type(
        cls, value: EdgeEntity | ViewEntity | PhysicalUnknownEntity, info: ValidationInfo
    ) -> DataType | EdgeEntity | ViewEntity | PhysicalUnknownEntity:
        if (connection := info.data.get("connection")) is None:
            if isinstance(value, ViewEntity):
                raise ValueError(
                    f"Missing connection type for property '{info.data.get('view_property', 'unknown')}'. This "
                    f"is required with value type pointing to another view."
                )
            return value
        if connection == "direct" and not isinstance(value, ViewEntity | PhysicalUnknownEntity):
            raise ValueError(f"Direct relation must have a value type that points to a view, got {value}")
        elif isinstance(connection, EdgeEntity) and not isinstance(value, ViewEntity):
            raise ValueError(f"Edge connection must have a value type that points to a view, got {value}")
        elif isinstance(connection, ReverseConnectionEntity) and not isinstance(value, ViewEntity):
            raise ValueError(f"Reverse connection must have a value type that points to a view, got {value}")
        return value

    @field_validator("default", mode="after")
    def set_proper_type_on_default(cls, value: Any, info: ValidationInfo) -> Any:
        if not value:
            return value
        value_type = info.data.get("value_type")
        if not isinstance(value_type, DataType):
            warnings.filterwarnings("default")
            warnings.warn(
                NeatValueWarning(f"Default value {value} set to connection {value_type} will be ignored"),
                stacklevel=2,
            )
            return None
        else:
            try:
                return value_type.convert_value(value)
            except ValueError:
                warnings.filterwarnings("default")
                warnings.warn(
                    NeatValueWarning(f"Could not convert {value} to {value_type}"),
                    stacklevel=2,
                )
                return None

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

    @field_validator("index", mode="after")
    @classmethod
    def index_set_correctly(cls, value: list[ContainerIndexEntity] | None, info: ValidationInfo) -> Any:
        if value is None:
            return value

        container = info.data["container"]
        container_property = info.data["container_property"]

        if not container or not container_property:
            raise ValueError("Container and container property must be set to use indexes")
        max_count = info.data.get("max_count")
        is_list = (
            max_count is not None and (isinstance(max_count, int | float) and max_count > 1)
        ) or max_count is float("inf")
        for index in value:
            if index.prefix is Undefined:
                message = f"The type of index is not defined. Please set 'inverted:{index!s}' or 'btree:{index!s}'."
                warnings.warn(
                    PropertyDefinitionWarning(str(container), "container property", str(container_property), message),
                    stacklevel=2,
                )
            elif index.prefix == "inverted" and not is_list:
                message = (
                    "It is not recommended to use inverted index on non-list properties. "
                    "Please consider using btree index instead."
                )
                warnings.warn(
                    PropertyDefinitionWarning(str(container), "container property", str(container_property), message),
                    stacklevel=2,
                )
            elif index.prefix == "btree" and is_list:
                message = (
                    "It is not recommended to use btree index on list properties. "
                    "Please consider using inverted index instead."
                )
                warnings.warn(
                    PropertyDefinitionWarning(str(container), "container property", str(container_property), message),
                    stacklevel=2,
                )
            if index.prefix == "inverted" and (index.cursorable is not None or index.by_space is not None):
                message = "Cursorable and bySpace are not supported for inverted indexes. These will be ignored."
                warnings.warn(
                    PropertyDefinitionWarning(str(container), "container property", str(container_property), message),
                    stacklevel=2,
                )
        return value

    @field_validator("constraint", mode="after")
    @classmethod
    def constraint_set_correctly(cls, value: ContainerConstraintListType | None, info: ValidationInfo) -> Any:
        if value is None:
            return value

        container = info.data["container"]
        container_property = info.data["container_property"]

        if not container or not container_property:
            raise ValueError("Container and container property must be set to use constraint")

        for constraint in value:
            if constraint.prefix is Undefined:
                message = f"The type of constraint is not defined. Please set 'uniqueness:{constraint!s}'."
                warnings.warn(
                    PropertyDefinitionWarning(str(container), "container property", str(container_property), message),
                    stacklevel=2,
                )
            elif constraint.prefix != "uniqueness":
                message = (
                    f"Unsupported constraint type on container property"
                    f" '{constraint.prefix}'. Currently only 'uniqueness' is supported."
                )
                raise ValueError(message) from None

            if len(constraint.suffix) > CONSTRAINT_ID_MAX_LENGTH:
                message = f"Constraint id '{constraint.suffix}' exceeds maximum length of {CONSTRAINT_ID_MAX_LENGTH}."
                raise ValueError(message) from None

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
        if (metadata := _metadata(info.context)) and isinstance(value, ConceptualEntity):
            if info.field_name == "container" and info.context.get("as_reference") is True:
                # When dumping as reference, the container should keep the default space for easy copying
                # over to user sheets.
                return value.dump()
            return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("connection", when_used="unless-none")
    def remove_defaults(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, ConceptualEntity) and (metadata := _metadata(info.context)):
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


class PhysicalContainer(SheetRow):
    container: ContainerEntityType = Field(
        alias="Container", description="Container id, strongly advised to PascalCase usage."
    )
    name: str | None = Field(
        alias="Name", default=None, description="Human readable name of the container being defined."
    )
    description: str | None = Field(
        alias="Description", default=None, description="Short description of the node being defined."
    )
    constraint: ContainerConstraintListType | None = Field(
        None, alias="Constraint", description="List of required (comma separated) constraints for the container"
    )
    used_for: Literal["node", "edge", "all"] | None = Field(
        "all", alias="Used For", description=" Whether the container is used for nodes, edges or all."
    )

    @field_validator("constraint", mode="after")
    @classmethod
    def constraint_set_correctly(cls, value: ContainerConstraintListType | None) -> Any:
        if value is None:
            return value

        for constraint in value:
            if constraint.prefix is Undefined:
                message = f"The type of constraint is not defined. Please set 'requires:{constraint!s}'."
                warnings.warn(
                    message,
                    stacklevel=2,
                )
            elif constraint.prefix != "requires":
                message = (
                    f"Unsupported constraint type on container as "
                    f"the whole '{constraint.prefix}'. Currently only 'requires' is supported."
                )
                raise ValueError(message) from None

            if len(constraint.suffix) > CONSTRAINT_ID_MAX_LENGTH:
                message = f"Constraint id '{constraint.suffix}' exceeds maximum length of {CONSTRAINT_ID_MAX_LENGTH}."
                raise ValueError(message) from None

            if constraint.require is None:
                message = (
                    f"Container constraint must have a container set. "
                    f"Please set 'requires:{constraint!s}(container=space:external_id)'."
                )
                raise ValueError(message) from None

        return value

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.container,)

    def as_container(self) -> dm.ContainerApply:
        container_id = self.container.as_id()
        constraints: dict[str, dm.Constraint] = {}
        for constraint in self.constraint or []:
            if constraint.require is None:
                continue
            requires = dm.RequiresConstraint(constraint.require.as_id())
            constraints[constraint.suffix] = requires

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
            if isinstance(value, PhysicalEntity):
                return value.dump(space=metadata.space, version=metadata.version)
            elif isinstance(value, ConceptualEntity):
                return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("constraint", when_used="unless-none")
    def remove_default_spaces(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _metadata(info.context)):
            return ",".join(
                constraint.dump(space=metadata.space, version=metadata.version)
                if isinstance(constraint, PhysicalEntity)
                else str(constraint)
                for constraint in value
            )
        return ",".join(str(value) for value in value)


class PhysicalView(SheetRow):
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
        True,
        alias="In Model",
        description="Indicates whether the view being defined is a part of the data model.",
    )
    conceptual: URIRefType | None = Field(
        None,
        alias="Conceptual",
        description="Used to make connection between physical and conceptual data model level",
    )

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.view,)

    @field_serializer("view", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _metadata(info.context)) and isinstance(value, ConceptualEntity):
            return value.dump(prefix=metadata.space, version=metadata.version)
        return str(value)

    @field_serializer("implements", when_used="unless-none")
    def remove_default_spaces(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _metadata(info.context)):
            return ",".join(
                parent.dump(space=metadata.space, version=metadata.version)
                if isinstance(parent, PhysicalEntity)
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


class PhysicalNodeType(SheetRow):
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
        if isinstance(value, PhysicalEntity) and (metadata := _metadata(info.context)):
            return value.dump(space=metadata.space, version=metadata.version)
        return str(value)


class PhysicalEnum(SheetRow):
    collection: ConceptEntityType = Field(alias="Collection", description="The collection this enum belongs to.")
    value: str = Field(alias="Value", description="The value of the enum.")
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the enum.")
    description: str | None = Field(alias="Description", default=None, description="Short description of the enum.")

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.collection, self.value

    @field_serializer("collection", when_used="unless-none")
    def remove_default_space(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, PhysicalEntity) and (metadata := _metadata(info.context)):
            return value.dump(space=metadata.space, version=metadata.version)
        return str(value)


class PhysicalDataModel(BaseVerifiedDataModel):
    metadata: PhysicalMetadata = Field(alias="Metadata", description="Contains information about the data model.")
    properties: SheetList[PhysicalProperty] = Field(
        alias="Properties", description="Contains the properties of the data model."
    )
    views: SheetList[PhysicalView] = Field(alias="Views", description="Contains the views of the data model.")
    containers: SheetList[PhysicalContainer] | None = Field(
        None,
        alias="Containers",
        description="Contains the definition containers that are the physical storage of the data model.",
    )
    enum: SheetList[PhysicalEnum] | None = Field(
        None, alias="Enum", description="Contains the definition of enum values."
    )
    nodes: SheetList[PhysicalNodeType] | None = Field(
        None, alias="Nodes", description="Contains the definition of the node types."
    )

    @model_validator(mode="after")
    def set_neat_id(self) -> "PhysicalDataModel":
        namespace = self.metadata.namespace

        for view in self.views:
            if not view.neatId:
                view.neatId = namespace[view.view.suffix]

        for property_ in self.properties:
            if not property_.neatId:
                property_.neatId = namespace[f"{property_.view.suffix}/{property_.view_property}"]

        return self

    def update_neat_id(self) -> None:
        """Update neat ids"""

        namespace = self.metadata.namespace

        for view in self.views:
            view.neatId = namespace[view.view.suffix]

        for property_ in self.properties:
            property_.neatId = namespace[f"{property_.view.suffix}/{property_.view_property}"]

    def sync_with_conceptual_data_model(self, conceptual_data_model: "ConceptualDataModel") -> None:
        # Sync at the metadata level
        if conceptual_data_model.metadata.physical == self.metadata.identifier:
            self.metadata.conceptual = conceptual_data_model.metadata.identifier
        else:
            # if models are not linked to start with, we skip
            return None

        conceptual_properties_by_neat_id = {prop.neatId: prop for prop in conceptual_data_model.properties}
        physical_properties_by_neat_id = {prop.neatId: prop for prop in self.properties}
        for neat_id, prop in conceptual_properties_by_neat_id.items():
            if prop.physical in physical_properties_by_neat_id:
                physical_properties_by_neat_id[prop.physical].conceptual = neat_id

        classes_by_neat_id = {cls.neatId: cls for cls in conceptual_data_model.concepts}
        views_by_neat_id = {view.neatId: view for view in self.views}
        for neat_id, class_ in classes_by_neat_id.items():
            if class_.physical in views_by_neat_id:
                views_by_neat_id[class_.physical].conceptual = neat_id

    def as_schema(self, instance_space: str | None = None, remove_cdf_spaces: bool = False) -> DMSSchema:
        from ._exporter import _DMSExporter

        return _DMSExporter(self, instance_space, remove_cdf_spaces=remove_cdf_spaces).to_schema()

    @classmethod
    def display_type_name(cls) -> str:
        return "VerifiedPhysicalModel"

    def _repr_html_(self) -> str:
        summary = {
            "level": self.metadata.level,
            "intended for": "Data Engineer",
            "name": self.metadata.name,
            "space": self.metadata.space,
            "external_id": self.metadata.external_id,
            "version": self.metadata.version,
            "views": len(self.views),
            "containers": len(self.containers) if self.containers else 0,
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
