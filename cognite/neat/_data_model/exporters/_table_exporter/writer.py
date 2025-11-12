import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from cognite.neat._data_model.importers._table_importer.data_classes import (
    DMSContainer,
    DMSEnum,
    DMSNode,
    DMSProperty,
    DMSView,
    MetadataValue,
    TableDMS,
)
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    DataType,
    DirectNodeRelation,
    EnumProperty,
    ListablePropertyTypeDefinition,
    NodeReference,
    RequestSchema,
    RequiresConstraintDefinition,
    UniquenessConstraintDefinition,
    ViewCorePropertyRequest,
    ViewReference,
    ViewRequest,
    ViewRequestProperty,
)
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    MultiEdgeProperty,
    MultiReverseDirectRelationPropertyRequest,
    ReverseDirectRelationProperty,
    SingleEdgeProperty,
    SingleReverseDirectRelationPropertyRequest,
)
from cognite.neat._data_model.models.entities import ParsedEntity


@dataclass
class ViewProperties:
    properties: list[DMSProperty] = field(default_factory=list)
    nodes: list[DMSNode] = field(default_factory=list)


@dataclass
class ContainerProperties:
    properties_by_id: dict[tuple[ContainerReference, str], dict] = field(default_factory=dict)
    enum_collections: list[DMSEnum] = field(default_factory=list)


class DMSTableWriter:
    def __init__(self, default_space: str, default_version: str, skip_properties_in_other_spaces: bool) -> None:
        self.default_space = default_space
        self.default_version = default_version
        self.skip_properties_in_other_spaces = skip_properties_in_other_spaces

    ## Main Entry Point ###
    def write_tables(self, schema: RequestSchema) -> TableDMS:
        metadata = self.write_metadata(schema.data_model)
        container_properties = self.write_container_properties(schema.containers)
        view_properties = self.write_view_properties(schema.views, container_properties)
        views = self.write_views(schema.views)
        containers = self.write_containers(schema.containers)

        return TableDMS(
            metadata=metadata,
            properties=view_properties.properties,
            views=views,
            containers=containers,
            enum=container_properties.enum_collections,
            nodes=view_properties.nodes,
        )

    ### Metadata Sheet ###
    @staticmethod
    def write_metadata(data_model: DataModelRequest) -> list[MetadataValue]:
        return [
            MetadataValue(key=key, value=value)
            for key, value in data_model.model_dump(
                mode="json", by_alias=True, exclude_none=True, exclude={"views"}
            ).items()
        ]

    ### Container Properties Sheet ###

    def write_containers(self, containers: list[ContainerRequest]) -> list[DMSContainer]:
        return [
            DMSContainer(
                container=self._create_container_entity(container),
                name=container.name,
                description=container.description,
                constraint=self._create_container_constraints(container),
                used_for=container.used_for,
            )
            for container in containers
        ]

    def write_container_properties(self, containers: list[ContainerRequest]) -> ContainerProperties:
        indices_by_container_property = self._write_container_indices(containers)
        constraints_by_container_property = self._write_container_property_constraints(containers)

        output = ContainerProperties()
        for container in containers:
            for prop_id, prop in container.properties.items():
                container_property = self._write_container_property(
                    container.as_reference(),
                    prop_id,
                    prop,
                    indices_by_container_property,
                    constraints_by_container_property,
                )
                output.properties_by_id[(container.as_reference(), prop_id)] = container_property
                if isinstance(prop.type, EnumProperty):
                    output.enum_collections.extend(
                        self._write_enum_collection(container.as_reference(), prop_id, prop.type)
                    )
        return output

    def _write_container_property(
        self,
        container_ref: ContainerReference,
        prop_id: str,
        prop: ContainerPropertyDefinition,
        indices_by_container_property: dict[tuple[ContainerReference, str], list[ParsedEntity]],
        constraints_by_container_property: dict[tuple[ContainerReference, str], list[ParsedEntity]],
    ) -> dict[str, Any]:
        return dict(
            connection=self._write_container_property_connection(prop.type),
            value_type=self._write_container_property_value_type(prop, prop_id, container_ref),
            min_count=0 if prop.nullable else 1,
            max_count=self._write_container_property_max_count(prop.type),
            immutable=prop.immutable,
            default=json.dumps(prop.default_value) if isinstance(prop.default_value, dict) else prop.default_value,
            auto_increment=prop.auto_increment,
            container=self._create_container_entity(container_ref),
            container_property=prop_id,
            container_property_name=prop.name,
            container_property_description=prop.description,
            index=indices_by_container_property.get((container_ref, prop_id)),
            constraint=constraints_by_container_property.get((container_ref, prop_id)),
        )

    def _write_container_property_connection(self, dtype: DataType) -> ParsedEntity | None:
        if not isinstance(dtype, DirectNodeRelation):
            return None
        properties: dict[str, str] = {}
        if dtype.container is not None:
            properties["container"] = str(self._create_container_entity(dtype.container))
        return ParsedEntity("", "direct", properties=properties)

    def _write_container_property_value_type(
        self, prop: ContainerPropertyDefinition, prop_id: str, container_ref: ContainerReference
    ) -> ParsedEntity:
        if isinstance(prop.type, DirectNodeRelation):
            # Will be overwritten if the view property has source set.
            return ParsedEntity("", "#N/A", properties={})
        elif isinstance(prop.type, EnumProperty):
            enum_properties = {"collection": self._enum_collection_name(container_ref, prop_id)}
            if prop.type.unknown_value is not None:
                enum_properties["unknownValue"] = prop.type.unknown_value
            return ParsedEntity("", "enum", properties=enum_properties)
        elif isinstance(prop.type, ListablePropertyTypeDefinition):
            # List and maxListSize are included in the maxCount of the property, so we exclude them here.
            entity_properties = prop.type.model_dump(
                mode="json", by_alias=True, exclude={"list", "maxListSize", "type"}, exclude_none=True
            )
            return ParsedEntity("", prop.type.type, properties=entity_properties)
        else:
            # Should not happen as all types are either ListablePropertyTypeDefinition or EnumProperty.
            return ParsedEntity("", prop.type.type, properties={})

    @staticmethod
    def _write_container_property_max_count(dtype: DataType) -> int | None:
        if isinstance(dtype, ListablePropertyTypeDefinition) and dtype.list:
            return dtype.max_list_size
        return 1

    @staticmethod
    def _write_container_indices(
        containers: list[ContainerRequest],
    ) -> dict[tuple[ContainerReference, str], list[ParsedEntity]]:
        """Writes container indices and groups them by (container_reference, property_id)."""
        indices_by_id: dict[tuple[ContainerReference, str], list[ParsedEntity]] = defaultdict(list)
        for container in containers:
            if not container.indexes:
                continue
            for index_id, index in container.indexes.items():
                for order, prop_id in enumerate(index.properties, 1):
                    entity_properties = index.model_dump(
                        mode="json", by_alias=True, exclude={"index_type", "properties"}, exclude_none=True
                    )
                    if len(index.properties) > 1:
                        entity_properties["order"] = str(order)
                    entity = ParsedEntity(index.index_type, index_id, properties=entity_properties)
                    indices_by_id[(container.as_reference(), prop_id)].append(entity)
        return indices_by_id

    @staticmethod
    def _write_container_property_constraints(
        containers: list[ContainerRequest],
    ) -> dict[tuple[ContainerReference, str], list[ParsedEntity]]:
        """Writes container constraints and groups them by (container_reference, property_id).

        Note this only includes uniqueness constraints, the require constraints is handled
        in the writing of the container itself.
        """
        constraints_by_id: dict[tuple[ContainerReference, str], list[ParsedEntity]] = defaultdict(list)
        for container in containers:
            if not container.constraints:
                continue
            for constraint_id, constraint in container.constraints.items():
                if not isinstance(constraint, UniquenessConstraintDefinition):
                    continue
                for order, prop_id in enumerate(constraint.properties, 1):
                    entity_properties = constraint.model_dump(
                        mode="json", by_alias=True, exclude={"constraint_type", "properties"}, exclude_none=True
                    )
                    if len(constraint.properties) > 1:
                        entity_properties["order"] = str(order)
                    entity = ParsedEntity(constraint.constraint_type, constraint_id, properties=entity_properties)
                    constraints_by_id[(container.as_reference(), prop_id)].append(entity)
        return constraints_by_id

    def _create_container_constraints(self, container: ContainerRequest) -> list[ParsedEntity] | None:
        if not container.constraints:
            return None
        output: list[ParsedEntity] = []
        for constraint_id, constraint in container.constraints.items():
            if not isinstance(constraint, RequiresConstraintDefinition):
                continue
            entity_properties = {"require": str(self._create_container_entity(constraint.require))}
            output.append(
                ParsedEntity(prefix=constraint.constraint_type, suffix=constraint_id, properties=entity_properties)
            )
        return output or None

    ### Enum Sheet ###
    @staticmethod
    def _enum_collection_name(container_ref: ContainerReference, prop_id: str) -> str:
        return f"{container_ref.external_id}.{prop_id}"

    def _write_enum_collection(
        self, container_ref: ContainerReference, prop_id: str, enum: EnumProperty
    ) -> list[DMSEnum]:
        output: list[DMSEnum] = []
        name = self._enum_collection_name(container_ref, prop_id)
        for value_id, value in enum.values.items():
            output.append(
                DMSEnum(
                    collection=name,
                    value=value_id,
                    name=value.name,
                    description=value.description,
                )
            )
        return output

    ### View Sheet ###
    def write_views(self, views: list[ViewRequest]) -> list[DMSView]:
        return [
            DMSView(
                view=self._create_view_entity(view),
                name=view.name,
                description=view.description,
                implements=[self._create_view_entity(parent) for parent in view.implements]
                if view.implements
                else None,
                filter=json.dumps(view.filter) if view.filter else None,
            )
            for view in views
        ]

    def write_view_properties(self, views: list[ViewRequest], container: ContainerProperties) -> ViewProperties:
        output = ViewProperties()
        for view in views:
            if not view.properties:
                continue
            if self.skip_properties_in_other_spaces and view.space != self.default_space:
                continue
            for prop_id, prop in view.properties.items():
                output.properties.append(self._write_view_property(view, prop_id, prop, container))
                if isinstance(prop, EdgeProperty):
                    output.nodes.append(self._write_node(prop))
        return output

    def _write_view_property(
        self, view: ViewRequest, prop_id: str, prop: ViewRequestProperty, container: ContainerProperties
    ) -> DMSProperty:
        container_properties: dict[str, Any] = {}
        if isinstance(prop, ViewCorePropertyRequest):
            identifier = (prop.container, prop.container_property_identifier)
            if identifier in container.properties_by_id:
                container_properties = container.properties_by_id[identifier]
        view_properties: dict[str, Any] = dict(
            view=self._create_view_entity(view), view_property=prop_id, name=prop.name, description=prop.description
        )
        if connection := self._write_view_property_connection(prop):
            view_properties["connection"] = connection
        if view_value_type := self._write_view_property_value_type(prop):
            view_properties["value_type"] = view_value_type
        view_min_count = self._write_view_property_min_count(prop)
        if view_min_count is not None:
            view_properties["min_count"] = view_min_count
        view_max_count = self._write_view_property_max_count(prop)
        if view_max_count != "container":
            view_properties["max_count"] = view_max_count

        # Overwrite container properties with view properties where relevant.
        args = container_properties | view_properties
        return DMSProperty(**args)

    def _write_view_property_connection(self, prop: ViewRequestProperty) -> ParsedEntity | None:
        if isinstance(prop, ViewCorePropertyRequest):
            # Use the container definition for connection
            return None
        elif isinstance(prop, EdgeProperty):
            edge_properties: dict[str, str] = {}
            if prop.direction != "outwards":
                edge_properties["direction"] = prop.direction
            if prop.edge_source is not None:
                edge_properties["edgeSource"] = str(self._create_view_entity(prop.edge_source))
            edge_properties["type"] = str(self._create_node_entity(prop.type))
            return ParsedEntity("", "edge", properties=edge_properties)
        elif isinstance(prop, ReverseDirectRelationProperty):
            return ParsedEntity("", "reverse", properties={"property": prop.through.identifier})
        else:
            raise ValueError(f"Unknown view property type: {type(prop)}")

    def _write_view_property_value_type(self, prop: ViewRequestProperty) -> ParsedEntity | None:
        if isinstance(prop, ViewCorePropertyRequest):
            if prop.source:
                return self._create_view_entity(prop.source)
            else:
                # Use the container definition for value type
                return None
        elif isinstance(prop, ReverseDirectRelationProperty | EdgeProperty):
            return self._create_view_entity(prop.source)
        else:
            raise ValueError(f"Unknown view property type: {type(prop)}")

    @staticmethod
    def _write_view_property_min_count(prop: ViewRequestProperty) -> int | None:
        if isinstance(prop, ViewCorePropertyRequest):
            # Use the container definition for min count
            return None
        # Edges and reverse relations cannot be required.
        return 0

    @staticmethod
    def _write_view_property_max_count(prop: ViewRequestProperty) -> int | None | Literal["container"]:
        if isinstance(prop, ViewCorePropertyRequest):
            # Use the container definition for max count
            return "container"
        elif isinstance(prop, SingleEdgeProperty | SingleReverseDirectRelationPropertyRequest):
            return 1
        elif isinstance(prop, MultiEdgeProperty | MultiReverseDirectRelationPropertyRequest):
            return None
        else:
            raise ValueError(f"Unknown view property type: {type(prop)}")

    ### Node Sheet ###

    def _write_node(self, prop: EdgeProperty) -> DMSNode:
        return DMSNode(node=self._create_node_entity(prop.type))

    ## Entity Helpers ###

    def _create_view_entity(self, view: ViewRequest | ViewReference) -> ParsedEntity:
        prefix = view.space
        properties = {"version": view.version}
        if view.space == self.default_space:
            prefix = ""
            if view.version == self.default_version:
                # Only use default version if space is also default.
                properties = {}
        return ParsedEntity(prefix=prefix, suffix=view.external_id, properties=properties)

    def _create_container_entity(self, container: ContainerRequest | ContainerReference) -> ParsedEntity:
        prefix = container.space
        if container.space == self.default_space:
            prefix = ""
        return ParsedEntity(prefix=prefix, suffix=container.external_id, properties={})

    def _create_node_entity(self, node: NodeReference) -> ParsedEntity:
        prefix = node.space
        if node.space == self.default_space:
            prefix = ""
        return ParsedEntity(prefix=prefix, suffix=node.external_id, properties={})
