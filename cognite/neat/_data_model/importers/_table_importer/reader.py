import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, cast, overload

from pydantic import BaseModel, TypeAdapter, ValidationError

from cognite.neat._data_model.models.dms import (
    Constraint,
    ConstraintAdapter,
    ContainerPropertyDefinition,
    ContainerRequest,
    DataModelRequest,
    Index,
    IndexAdapter,
    NodeReference,
    RequestSchema,
    SpaceRequest,
    UniquenessConstraintDefinition,
    ViewRequest,
    ViewRequestProperty,
    ViewRequestPropertyAdapter,
)
from cognite.neat._data_model.models.entities import ParsedEntity, parse_entity
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import DMSContainer, DMSEnum, DMSNode, DMSProperty, DMSView, TableDMS
from .source import TableSource

T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)


@dataclass
class ReadViewProperty:
    prop_id: str
    row_no: int
    view_property: ViewRequestProperty


@dataclass
class ReadContainerProperty:
    prop_id: str
    row_no: int
    container_property: ContainerPropertyDefinition


@dataclass
class ReadIndex:
    prop_id: str
    order: int | None
    row_no: int
    index_id: str
    index: Index


@dataclass
class ReadConstraint:
    prop_id: str
    order: int | None
    row_no: int
    constraint_id: str
    constraint: Constraint


@dataclass
class ReadProperties:
    """Read properties from the properties table.

    Attributes:
        container: A mapping from container entity to a mapping of property identifier to container property definition.
        view: A mapping from view entity to a mapping of property identifier to view property definition.
        indices: A mapping from (container entity, index identifier) to a list of read indices
        constraints: A mapping from (container entity, constraint identifier) to a list of read constraints
    """

    container: dict[tuple[ParsedEntity, str], list[ReadContainerProperty]] = field(
        default_factory=lambda: defaultdict(list)
    )
    view: dict[tuple[ParsedEntity, str], list[ReadViewProperty]] = field(default_factory=lambda: defaultdict(list))
    indices: dict[tuple[ParsedEntity, str], list[ReadIndex]] = field(default_factory=lambda: defaultdict(list))
    constraints: dict[tuple[ParsedEntity, str], list[ReadConstraint]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class ProcessedProperties:
    container: dict[ParsedEntity, dict[str, ContainerPropertyDefinition]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    view: dict[ParsedEntity, dict[str, ViewRequestProperty]] = field(default_factory=lambda: defaultdict(dict))
    indices: dict[ParsedEntity, dict[str, Index]] = field(default_factory=lambda: defaultdict(dict))
    constraints: dict[ParsedEntity, dict[str, Constraint]] = field(default_factory=lambda: defaultdict(dict))


class DMSTableReader:
    class Sheet:
        metadata = cast(str, TableDMS.model_fields["metadata"].validation_alias)
        properties = cast(str, TableDMS.model_fields["properties"].validation_alias)
        containers = cast(str, TableDMS.model_fields["containers"].validation_alias)
        views = cast(str, TableDMS.model_fields["views"].validation_alias)
        nodes = cast(str, TableDMS.model_fields["nodes"].validation_alias)

    class PropertyColumn:
        view = cast(str, DMSProperty.model_fields["view"].validation_alias)
        view_property = cast(str, DMSProperty.model_fields["view_property"].validation_alias)
        connection = cast(str, DMSProperty.model_fields["connection"].validation_alias)
        value_type = cast(str, DMSProperty.model_fields["value_type"].validation_alias)
        min_count = cast(str, DMSProperty.model_fields["min_count"].validation_alias)
        max_count = cast(str, DMSProperty.model_fields["max_count"].validation_alias)
        default = cast(str, DMSProperty.model_fields["default"].validation_alias)
        auto_increment = cast(str, DMSProperty.model_fields["auto_increment"].validation_alias)
        container = cast(str, DMSProperty.model_fields["container"].validation_alias)
        container_property = cast(str, DMSProperty.model_fields["container_property"].validation_alias)
        container_property_name = cast(str, DMSProperty.model_fields["container_property_name"].validation_alias)
        container_property_description = cast(
            str, DMSProperty.model_fields["container_property_description"].validation_alias
        )
        index = cast(str, DMSProperty.model_fields["index"].validation_alias)
        constraint = cast(str, DMSProperty.model_fields["constraint"].validation_alias)

    class ContainerColumn:
        container = cast(str, DMSContainer.model_fields["container"].validation_alias)

    class ViewColumn:
        view = cast(str, DMSView.model_fields["view"].validation_alias)
        filter = cast(str, DMSView.model_fields["filter"].validation_alias)

    def __init__(self, default_space: str, default_version: str, source: TableSource) -> None:
        self.default_space = default_space
        self.default_version = default_version
        self.source = source
        self.errors: list[ModelSyntaxError] = []

    def read_tables(self, tables: TableDMS) -> RequestSchema:
        space_request = self.read_space(self.default_space)
        node_types = self.read_nodes(tables.nodes)
        enum_collections = self.read_enum_collections(tables.enum)
        read = self.read_properties(tables.properties, enum_collections)
        processed = self.process_properties(read)
        containers = self.read_containers(tables.containers, processed)
        views, valid_view_entities = self.read_views(tables.views, processed.view)
        data_model = self.read_data_model(tables, valid_view_entities)

        if self.errors:
            raise ModelImportError(self.errors) from None
        return RequestSchema(
            dataModel=data_model, views=views, containers=containers, spaces=[space_request], nodeTypes=node_types
        )

    def read_space(self, space: str) -> SpaceRequest:
        space_request = self._validate_obj(SpaceRequest, {"space": space}, (self.Sheet.metadata,), field_name="value")
        if space_request is None:
            # If space is invalid, we stop parsing to avoid raising an error for every place the space is used.
            raise ModelImportError(self.errors) from None
        return space_request

    def read_nodes(self, nodes: list[DMSNode]) -> list[NodeReference]:
        node_refs: list[NodeReference] = []
        for row_no, row in enumerate(nodes):
            data = self._create_node_ref(row.node)
            parsed = self._validate_obj(NodeReference, data, (self.Sheet.nodes, row_no))
            if parsed is not None:
                node_refs.append(parsed)
        return node_refs

    @staticmethod
    def read_enum_collections(enum_rows: list[DMSEnum]) -> dict[str, dict[str, Any]]:
        enum_collections: dict[str, dict[str, Any]] = defaultdict(dict)
        for row in enum_rows:
            enum_collections[row.collection][row.value] = {
                "name": row.name,
                "description": row.description,
            }
        return enum_collections

    def read_properties(
        self, properties: list[DMSProperty], enum_collections: dict[str, dict[str, Any]]
    ) -> ReadProperties:
        read = ReadProperties()
        for row_no, prop in enumerate(properties):
            self._process_view_property(prop, read, row_no)
            if prop.container is None or prop.container_property is None:
                continue
            self._process_container_property(prop, read, enum_collections, row_no)
            self._process_index(prop, read, row_no)
            self._process_constraint(prop, read, row_no)
        return read

    def process_properties(self, read: ReadProperties) -> ProcessedProperties:
        return ProcessedProperties(
            container=self.create_container_properties(read),
            view=self.create_view_properties(read),
            indices=self.create_indices(read),
            constraints=self.create_constraints(read),
        )

    def create_container_properties(
        self, read: ReadProperties
    ) -> dict[ParsedEntity, dict[str, ContainerPropertyDefinition]]:
        container_props: dict[ParsedEntity, dict[str, ContainerPropertyDefinition]] = defaultdict(dict)
        for (container_entity, prop_id), prop_list in read.container.items():
            if len(prop_list) == 0:
                # Should not happen
                continue
            container_props[container_entity][prop_id] = prop_list[0].container_property
            if len(prop_list) > 1 and self._are_definitions_different(prop_list):
                rows_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheet.properties, p.row_no) for p in prop_list]
                )
                container_columns_str = humanize_collection(
                    [
                        self.PropertyColumn.connection,
                        self.PropertyColumn.value_type,
                        self.PropertyColumn.min_count,
                        self.PropertyColumn.max_count,
                        self.PropertyColumn.default,
                        self.PropertyColumn.auto_increment,
                        self.PropertyColumn.container_property_name,
                        self.PropertyColumn.container_property_description,
                        self.PropertyColumn.index,
                        self.PropertyColumn.constraint,
                    ]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheet.properties,))} "
                            f"when the column {self.PropertyColumn.container!r} and "
                            f"{self.PropertyColumn.container_property!r} are the same, "
                            f"all the container columns ({container_columns_str}) must be the same. "
                            f"Inconsistent definitions for container '{container_entity!s} "
                            f"and {prop_id!r}' found in rows {rows_str}."
                        )
                    )
                )
        return container_props

    def _are_definitions_different(self, prop_list: list[ReadContainerProperty]) -> bool:
        if len(prop_list) < 2:
            return False
        first_def = prop_list[0].container_property
        for prop in prop_list[1:]:
            if first_def != prop.container_property:
                return True
        return False

    def create_view_properties(self, read: ReadProperties) -> dict[ParsedEntity, dict[str, ViewRequestProperty]]:
        view_props: dict[ParsedEntity, dict[str, ViewRequestProperty]] = defaultdict(dict)
        for (view_entity, prop_id), prop_list in read.view.items():
            if len(prop_list) == 0:
                # Should not happen
                continue
            view_props[view_entity][prop_id] = prop_list[0].view_property
            if len(prop_list) > 1:
                rows_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheet.properties, p.row_no) for p in prop_list]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheet.properties,))} the combination of columns "
                            f"{self.PropertyColumn.view!r} and {self.PropertyColumn.view_property!r} must be unique. "
                            f"Duplicated entries for view '{view_entity!s}' and "
                            f"property '{prop_id!s}' found in rows {rows_str}."
                        )
                    )
                )

        return view_props

    def create_indices(self, read: ReadProperties) -> dict[ParsedEntity, dict[str, Index]]:
        indices: dict[ParsedEntity, dict[str, Index]] = defaultdict(dict)
        for (container_entity, index_id), index_list in read.indices.items():
            if len(index_list) == 0:
                continue
            index = index_list[0].index
            if len(index_list) == 1:
                indices[container_entity][index_id] = index
                continue
            if missing_order := [idx for idx in index_list if idx.order is None]:
                row_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheet.properties, idx.row_no) for idx in missing_order]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In table {self.Sheet.properties!r} column {self.PropertyColumn.index!r}: "
                            f"the index {index_id!r} on container {container_entity!s} is defined on multiple "
                            f"properties. This requires the 'order' attribute to be set. It is missing in rows "
                            f"{row_str}."
                        )
                    )
                )
                continue
            index.properties = [idx.prop_id for idx in sorted(index_list, key=lambda x: x.order or 999)]
            indices[container_entity][index_id] = index
        return indices

    def create_constraints(self, read: ReadProperties) -> dict[ParsedEntity, dict[str, Constraint]]:
        constraints: dict[ParsedEntity, dict[str, Constraint]] = defaultdict(dict)
        for (container_entity, constraint_id), constraint_list in read.constraints.items():
            if len(constraint_list) == 0:
                continue
            constraint = constraint_list[0].constraint
            if len(constraint_list) == 1 or not isinstance(constraint, UniquenessConstraintDefinition):
                constraints[container_entity][constraint_id] = constraint
                continue
            if missing_order := [c for c in constraint_list if c.order is None]:
                row_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheet.properties, c.row_no) for c in missing_order]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In table {self.Sheet.properties!r} column {self.PropertyColumn.constraint!r}: "
                            f"the uniqueness constraint {constraint_id!r} on container {container_entity!s} is defined "
                            f"on multiple properties. This requires the 'order' attribute to be set. It is missing in "
                            f"rows {row_str}."
                        )
                    )
                )
                continue
            constraint.properties = [c.prop_id for c in sorted(constraint_list, key=lambda x: x.order or 999)]
            constraints[container_entity][constraint_id] = constraint
        return constraints

    def _process_view_property(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        loc = (self.Sheet.properties, row_no)
        data = self.read_view_property(prop, loc)
        view_prop = self._validate_adapter(ViewRequestPropertyAdapter, data, loc)
        if view_prop is not None:
            read.view[(prop.view, prop.view_property)].append(
                # MyPy has a very strange complaint here. It complains that given type is not expected type,
                # even though they are exactly the same.
                ReadViewProperty(prop.container_property, row_no, view_prop)  # type: ignore[arg-type]
            )
        return None

    def _process_container_property(
        self, prop: DMSProperty, read: ReadProperties, enum_collections: dict[str, dict[str, Any]], row_no: int
    ) -> None:
        loc = (self.Sheet.properties, row_no)
        data = self.read_container_property(prop, enum_collections, loc=loc)
        container_prop = self._validate_obj(ContainerPropertyDefinition, data, loc)
        if container_prop is not None and prop.container and prop.container_property:
            read.container[(prop.container, prop.container_property)].append(
                ReadContainerProperty(prop.container_property, row_no, container_prop)
            )
        return None

    def _process_index(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        if prop.index is None or prop.container_property is None or prop.container is None:
            return

        loc = (self.Sheet.properties, row_no, self.PropertyColumn.index)
        for index in prop.index:
            data = self.read_index(index, prop.container_property)
            created = self._validate_adapter(IndexAdapter, data, loc)
            if created is None:
                continue
            order = self._read_order(index.properties, loc)
            read.indices[(prop.container, index.suffix)].append(
                ReadIndex(
                    prop_id=prop.container_property, order=order, row_no=row_no, index_id=index.suffix, index=created
                )
            )

    def _read_order(self, properties: dict[str, Any], loc: tuple[str | int, ...]) -> int | None:
        if "order" not in properties:
            return None
        try:
            return int(properties["order"])
        except ValueError:
            self.errors.append(
                ModelSyntaxError(
                    message=f"In {self.source.location(loc)} invalid order value '{properties['order']}'. "
                    "Must be an integer."
                )
            )
            return None

    @staticmethod
    def read_index(index: ParsedEntity, prop_id: str) -> dict[str, Any]:
        return {
            "indexType": index.prefix,
            "properties": [prop_id],
            **index.properties,
        }

    def _process_constraint(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        if prop.constraint is None or prop.container_property is None or prop.container is None:
            return
        loc = (self.Sheet.properties, row_no, self.PropertyColumn.constraint)
        for constraint in prop.constraint:
            data = self.read_constraint(constraint, prop.container_property)
            created = self._validate_adapter(ConstraintAdapter, data, loc)
            if created is None:
                continue
            order = self._read_order(constraint.properties, loc)
            read.constraints[(prop.container, constraint.suffix)].append(
                ReadConstraint(
                    prop_id=prop.container_property,
                    order=order,
                    constraint_id=constraint.suffix,
                    row_no=row_no,
                    constraint=created,
                )
            )

    @staticmethod
    def read_constraint(constraint: ParsedEntity, prop_id: str) -> dict[str, Any]:
        return {"constraintType": constraint.prefix, "properties": [prop_id], **constraint.properties}

    def read_view_property(self, prop: DMSProperty, loc: tuple[str | int, ...]) -> dict[str, Any]:
        """Reads a single view property from a given row in the properties table.

        The type of property (core, edge, reverse direct relation) is determined based on the connection column
        as follows:
        1. If the connection is empty or 'direct' it is a core property.
        2. If the connection is 'edge' it is an edge property.
        3. If the connection is 'reverse' it is a reverse direct relation property
        4. Otherwise, it is an error.

        Args:
            prop (DMSProperty): The property row to read.
            loc (tuple[str | int, ...]): The location of the property in the source for error reporting.

        Returns:
            ViewRequestProperty: The parsed view property.
        """

        if prop.connection is None or prop.connection.suffix == "direct":
            return self.read_core_view_property(prop)
        elif prop.connection.suffix == "edge":
            return self.read_edge_view_property(prop, loc)
        elif prop.connection.suffix == "reverse":
            return self.read_reverse_direct_relation_view_property(prop)
        else:
            raise ValueError()

    def read_core_view_property(self, prop: DMSProperty) -> dict[str, Any]:
        return dict(
            connectionType="primary_property",
            name=prop.name,
            description=prop.description,
            container=self._create_container_ref(prop.container),
            containerPropertyIdentifier=prop.container_property,
            source=None if prop.connection is None else self._create_view_ref(prop.value_type),
        )

    def read_edge_view_property(self, prop: DMSProperty, loc: tuple[str | int, ...]) -> dict[str, Any]:
        if prop.connection is None:
            return {}
        edge_source: dict[str, str | None] | None = None
        if "edgeSource" in prop.connection.properties:
            edge_source = self._create_view_ref_unparsed(
                prop.connection.properties["edgeSource"], (*loc, self.PropertyColumn.connection, "edgeSource")
            )
        return dict(
            connectionType="single_edge_connection" if prop.max_count == 1 else "multi_edge_connection",
            name=prop.name,
            description=prop.description,
            source=self._create_view_ref(prop.value_type),
            type=self._create_node_ref_unparsed(
                prop.connection.properties.get("type"),
                prop.view,
                prop.view_property,
                (*loc, self.PropertyColumn.connection, "type"),
            ),
            edgeSource=edge_source,
            direction=prop.connection.properties.get("direction", "outwards"),
        )

    def read_reverse_direct_relation_view_property(
        self,
        prop: DMSProperty,
    ) -> dict[str, Any]:
        if prop.connection is None:
            return {}
        view_ref = self._create_view_ref(prop.value_type)
        return dict(
            connectionType="single_reverse_direct_relation" if prop.max_count == 1 else "multi_reverse_direct_relation",
            name=prop.name,
            description=prop.description,
            source=view_ref,
            through={
                "source": view_ref,
                "identifier": prop.connection.properties.get("property"),
            },
        )

    def read_container_property(
        self, prop: DMSProperty, enum_collections: dict[str, dict[str, Any]], loc: tuple[str | int, ...]
    ) -> dict[str, Any]:
        data_type = self._read_data_type(prop, enum_collections, loc)
        return dict(
            immutable=prop.immutable,
            nullable=prop.min_count == 0 or prop.min_count is None,
            autoIncrement=prop.auto_increment,
            defaultValue=prop.default,
            description=prop.container_property_description,
            name=prop.container_property_name,
            type=data_type,
        )

    def _read_data_type(
        self, prop: DMSProperty, enum_collections: dict[str, dict[str, Any]], loc: tuple[str | int, ...]
    ) -> dict[str, Any]:
        # Implementation to read the container property type from DMSProperty
        is_list = None if prop.max_count is None else prop.max_count > 1
        max_list_size: int | None = None
        if is_list and prop.max_count is not None:
            max_list_size = prop.max_count

        args: dict[str, Any] = {
            "maxListSize": max_list_size,
            "list": is_list,
            "type": "direct" if prop.connection is not None else prop.value_type.suffix,
        }
        args.update(prop.value_type.properties)
        if "container" in args and prop.connection is not None:
            # Direct relation constraint.
            args["container"] = self._create_container_ref_unparsed(
                prop.connection.properties["container"], (*loc, self.PropertyColumn.connection, "container")
            )
        if args["type"] == "enum" and "collection" in prop.value_type.properties:
            args["values"] = enum_collections.get(prop.value_type.properties["collection"], {})
        return args

    def read_containers(
        self, containers: list[DMSContainer], properties: ProcessedProperties
    ) -> list[ContainerRequest]:
        # Implementation to read containers from DMSContainer list
        containers_requests: list[ContainerRequest] = []
        rows_by_seen: dict[ParsedEntity, list[int]] = defaultdict(list)
        for row_no, container in enumerate(containers):
            container_request = self._validate_obj(
                ContainerRequest,
                dict(
                    **self._create_container_ref(container.container),
                    usedFor=container.used_for,
                    name=container.name,
                    description=container.description,
                    properties=properties.container[container.container],
                    indexes=properties.indices.get(container.container),
                    constraints=properties.constraints.get(container.container),
                ),
                (self.Sheet.containers, row_no),
            )
            if container_request is None:
                continue
            if container.container in rows_by_seen:
                rows_by_seen[container.container].append(row_no)
            else:
                containers_requests.append(container_request)
                rows_by_seen[container.container] = [row_no]
        for entity, rows in rows_by_seen.items():
            if len(rows) > 1:
                rows_str = humanize_collection([self.source.adjust_row_number(self.Sheet.containers, r) for r in rows])
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheet.containers,))} the values in "
                            f"column {self.ContainerColumn.container!r} must be unique. "
                            f"Duplicated entries for container '{entity!s}' found in rows {rows_str}."
                        )
                    )
                )
        return containers_requests

    def read_views(
        self,
        views: list[DMSView],
        properties: dict[ParsedEntity, dict[str, ViewRequestProperty]],
    ) -> tuple[list[ViewRequest], set[ParsedEntity]]:
        views_requests: list[ViewRequest] = []
        rows_by_seen: dict[ParsedEntity, list[int]] = defaultdict(list)
        for row_no, view in enumerate(views):
            filter_dict: dict[str, Any] | None = None
            if view.filter is not None:
                try:
                    filter_dict = json.loads(view.filter)
                except ValueError as e:
                    self.errors.append(
                        ModelSyntaxError(
                            message=(
                                f"In {self.source.location((self.Sheet.views, row_no, self.ViewColumn.filter))} "
                                f"must be valid json. Got error {e!s}"
                            )
                        )
                    )
            view_request = self._validate_obj(
                ViewRequest,
                dict(
                    **self._create_view_ref(view.view),
                    name=view.name,
                    description=view.description,
                    implements=[self._create_view_ref(impl) for impl in view.implements] if view.implements else None,
                    filter=filter_dict,
                    properties=properties.get(view.view, {}),
                ),
                (self.Sheet.views, row_no),
            )
            if view_request is None:
                continue
            if view.view in rows_by_seen:
                rows_by_seen[view.view].append(row_no)
            else:
                views_requests.append(view_request)
                rows_by_seen[view.view] = [row_no]
        for entity, rows in rows_by_seen.items():
            if len(rows) > 1:
                rows_str = humanize_collection([self.source.adjust_row_number(self.Sheet.views, r) for r in rows])
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheet.views,))} the values in "
                            f"column {self.ViewColumn.view!r} must be unique. "
                            f"Duplicated entries for view '{entity!s}' found in rows {rows_str}."
                        )
                    )
                )
        return views_requests, set(rows_by_seen.keys())

    def read_data_model(self, tables: TableDMS, valid_view_entities: set[ParsedEntity]) -> DataModelRequest:
        data = {
            **{meta.name: meta.value for meta in tables.metadata},
            "views": [
                self._create_view_ref(view.view)
                for view in tables.views
                if view.in_model is not False and view.view in valid_view_entities
            ],
        }
        model = self._validate_obj(DataModelRequest, data, (self.Sheet.metadata,), field_name="value")
        if model is None:
            # This is the last step, so we can raise the error here.
            raise ModelImportError(self.errors) from None
        return model

    def _parse_entity(self, entity: str, loc: tuple[str | int, ...]) -> ParsedEntity | None:
        try:
            parsed = parse_entity(entity)
        except ValueError as e:
            self.errors.append(
                ModelSyntaxError(message=f"In {self.source.location(loc)} failed to parse entity '{entity}': {e!s}")
            )
            return None
        return parsed

    def _create_view_ref_unparsed(self, entity: str, loc: tuple[str | int, ...]) -> dict[str, str | None]:
        parsed = self._parse_entity(entity, loc)
        if parsed is None:
            return dict()
        return self._create_view_ref(parsed)

    def _create_view_ref(self, entity: ParsedEntity | None) -> dict[str, str | None]:
        if entity is None or entity.suffix == "":
            # If no suffix is given, we cannot create a valid reference.
            return dict()
        space, version = entity.prefix, entity.properties.get("version")
        if space == "":
            space = self.default_space
            # Only if default space is used, we can use default version.
            if version is None:
                version = self.default_version
        return {
            "space": space,
            "externalId": entity.suffix,
            "version": version,
        }

    def _create_container_ref_unparsed(self, entity: str, loc: tuple[str | int, ...]) -> dict[str, str]:
        parsed = self._parse_entity(entity, loc)
        if parsed is None:
            return dict()
        return self._create_container_ref(parsed)

    def _create_container_ref(self, entity: ParsedEntity | None) -> dict[str, str]:
        if entity is None or entity.suffix == "":
            # If no suffix is given, we cannot create a valid reference.
            return dict()
        return {
            "space": entity.prefix or self.default_space,
            "externalId": entity.suffix,
        }

    def _create_node_ref_unparsed(
        self, entity: str | None, view: ParsedEntity, view_prop: str, loc: tuple[str | int, ...]
    ) -> dict[str, str | None]:
        if entity is None:
            # Use default
            return self._create_node_ref(None, view, view_prop)
        parsed = self._parse_entity(entity, loc)
        if parsed is None:
            return dict()
        return self._create_node_ref(parsed, view, view_prop)

    @overload
    def _create_node_ref(
        self, entity: ParsedEntity, *, view: None = None, view_prop: None = None
    ) -> dict[str, str | None]: ...

    @overload
    def _create_node_ref(
        self, entity: ParsedEntity | None, view: ParsedEntity, view_prop: str
    ) -> dict[str, str | None]: ...

    def _create_node_ref(
        self, entity: ParsedEntity | None, view: ParsedEntity | None = None, view_prop: str | None = None
    ) -> dict[str, str | None]:
        if entity is None or entity.suffix == "":
            if view is None or view_prop is None:
                return dict()
            # If no suffix is given, we fallback to the view's property
            return {
                "space": view.prefix or self.default_space,
                "externalId": f"{view.suffix}.{view_prop}",
            }
        return {
            "space": entity.prefix or self.default_space,
            "externalId": entity.suffix,
        }

    def _validate_obj(
        self,
        obj: type[T_BaseModel],
        data: dict,
        parent_loc: tuple[str | int, ...],
        field_name: Literal["field", "column", "value"] = "column",
    ) -> T_BaseModel | None:
        try:
            return obj.model_validate(data)
        except ValidationError as e:
            self._add_error_messages(e, parent_loc, field_name=field_name)
            return None

    def _validate_adapter(
        self, adapter: TypeAdapter[T_BaseModel], data: dict[str, Any], parent_loc: tuple[str | int, ...]
    ) -> T_BaseModel | None:
        try:
            return adapter.validate_python(data, strict=True)
        except ValidationError as e:
            self._add_error_messages(e, parent_loc, field_name="column")
            return None

    def _add_error_messages(
        self,
        error: ValidationError,
        parent_loc: tuple[str | int, ...],
        field_name: Literal["field", "column", "value"] = "column",
    ) -> None:
        seen: set[str] = set()
        for message in humanize_validation_error(
            error,
            parent_loc=parent_loc,
            humanize_location=self.source.location,
            field_name=field_name,
            field_renaming=self.source.field_mapping(parent_loc[0]),
        ):
            if message in seen:
                continue
            seen.add(message)
            self.errors.append(ModelSyntaxError(message=message))
