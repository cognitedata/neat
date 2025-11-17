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
from cognite.neat._exceptions import DataModelImportException
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
    """Reads a TableDMS object and converts it to a RequestSchema.


    Args:
        default_space (str): The default space to use when no space is given in an entity.
        default_version (str): The default version to use when no version is given in an entity.
        source (TableSource): The source of the table data, used for error reporting.

    Raises:
        DataModelImportError: If there are any errors in the data model.

    Attributes:
        errors (list[ModelSyntaxError]): A list of errors encountered during parsing.

    Class Attributes:
        Sheets: This is used to create error messages. It ensures that the column names matches
            the names in the table, even if they are renamed in the code.
        PropertyColumns: This is used to create error messages for the properties table.
            It ensures that the column names matches the names in the table, even if they are renamed in the code.
        ContainerColumns: This is used to create error messages for the containers table.
            It ensures that the column names matches the names in the table, even if they are renamed in the code.
        ViewColumns: This is used to create error messages for the views table.
            It ensures that the column names matches the names in the table, even if they are renamed in the code.

    """

    CELL_MISSING = "#N/A"

    # The following classes are used when creating error messages. They ensure that the column names
    # matches the names in the table, even if they are renamed in the code.
    # Note that this is not a complete list of all columns, only those that are used in error messages.
    class Sheets:
        metadata = cast(str, TableDMS.model_fields["metadata"].validation_alias)
        properties = cast(str, TableDMS.model_fields["properties"].validation_alias)
        containers = cast(str, TableDMS.model_fields["containers"].validation_alias)
        views = cast(str, TableDMS.model_fields["views"].validation_alias)
        nodes = cast(str, TableDMS.model_fields["nodes"].validation_alias)

    class PropertyColumns:
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

    class ContainerColumns:
        container = cast(str, DMSContainer.model_fields["container"].validation_alias)
        constraint = cast(str, DMSContainer.model_fields["constraint"].validation_alias)

    class ViewColumns:
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
            raise DataModelImportException(self.errors) from None
        return RequestSchema(
            dataModel=data_model, views=views, containers=containers, spaces=[space_request], nodeTypes=node_types
        )

    def read_space(self, space: str) -> SpaceRequest:
        space_request = self._validate_obj(SpaceRequest, {"space": space}, (self.Sheets.metadata,), field_name="value")
        if space_request is None:
            # If space is invalid, we stop parsing to avoid raising an error for every place the space is used.
            raise DataModelImportException(self.errors) from None
        return space_request

    def read_nodes(self, nodes: list[DMSNode]) -> list[NodeReference]:
        node_refs: list[NodeReference] = []
        for row_no, row in enumerate(nodes):
            data = self._create_node_ref(row.node)
            instantiated = self._validate_obj(NodeReference, data, (self.Sheets.nodes, row_no))
            if instantiated is not None:
                node_refs.append(instantiated)
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
                # This is when the property is an edge or reverse direct relation property.
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
                # If multiple view properties are mapping to the same container property,
                # the container property definitions must be the same.
                rows_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheets.properties, p.row_no) for p in prop_list]
                )
                container_columns_str = humanize_collection(
                    [
                        self.PropertyColumns.connection,
                        self.PropertyColumns.value_type,
                        self.PropertyColumns.min_count,
                        self.PropertyColumns.max_count,
                        self.PropertyColumns.default,
                        self.PropertyColumns.auto_increment,
                        self.PropertyColumns.container_property_name,
                        self.PropertyColumns.container_property_description,
                        self.PropertyColumns.index,
                        self.PropertyColumns.constraint,
                    ]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheets.properties,))} "
                            f"when the column {self.PropertyColumns.container!r} and "
                            f"{self.PropertyColumns.container_property!r} are the same, "
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
                # Safeguard against duplicated rows for view properties.
                rows_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheets.properties, p.row_no) for p in prop_list]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheets.properties,))} the combination of columns "
                            f"{self.PropertyColumns.view!r} and {self.PropertyColumns.view_property!r} must be unique. "
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
            # Remove duplicates based on prop_id, keeping the first occurrence
            # Note that we have already validated that the index definitions are the same
            index_list = list({read_index.prop_id: read_index for read_index in index_list}.values())
            index = index_list[0].index
            if len(index_list) == 1:
                indices[container_entity][index_id] = index
                continue
            if missing_order := [idx for idx in index_list if idx.order is None]:
                row_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheets.properties, idx.row_no) for idx in missing_order]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In table {self.Sheets.properties!r} column {self.PropertyColumns.index!r}: "
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
            # Remove duplicates based on prop_id, keeping the first occurrence
            # Note that we have already validated that the constraint definitions are the same
            constraint_list = list(
                {read_constraint.prop_id: read_constraint for read_constraint in constraint_list}.values()
            )
            constraint = constraint_list[0].constraint
            if len(constraint_list) == 1 or not isinstance(constraint, UniquenessConstraintDefinition):
                constraints[container_entity][constraint_id] = constraint
                continue
            if missing_order := [c for c in constraint_list if c.order is None]:
                row_str = humanize_collection(
                    [self.source.adjust_row_number(self.Sheets.properties, c.row_no) for c in missing_order]
                )
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In table {self.Sheets.properties!r} column {self.PropertyColumns.constraint!r}: "
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
        loc = (self.Sheets.properties, row_no)
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
        loc = (self.Sheets.properties, row_no)
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

        loc = (self.Sheets.properties, row_no, self.PropertyColumns.index)
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
        loc = (self.Sheets.properties, row_no, self.PropertyColumns.constraint)
        for constraint in prop.constraint:
            data = self.read_property_constraint(constraint, prop.container_property)
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
    def read_property_constraint(constraint: ParsedEntity, prop_id: str) -> dict[str, Any]:
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
            self.errors.append(
                ModelSyntaxError(
                    message=f"In {self.source.location(loc)} invalid connection type '{prop.connection.suffix}'. "
                )
            )
            return {}

    def read_core_view_property(self, prop: DMSProperty) -> dict[str, Any]:
        source: dict[str, str | None] | None = None
        if prop.connection is not None and prop.value_type.suffix != self.CELL_MISSING:
            source = self._create_view_ref(prop.value_type)

        return dict(
            connectionType="primary_property",
            name=prop.name,
            description=prop.description,
            container=self._create_container_ref(prop.container),
            containerPropertyIdentifier=prop.container_property,
            source=source,
        )

    def read_edge_view_property(self, prop: DMSProperty, loc: tuple[str | int, ...]) -> dict[str, Any]:
        if prop.connection is None:
            return {}
        edge_source: dict[str, str | None] | None = None
        if "edgeSource" in prop.connection.properties:
            edge_source = self._create_view_ref_unparsed(
                prop.connection.properties["edgeSource"], (*loc, self.PropertyColumns.connection, "edgeSource")
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
                (*loc, self.PropertyColumns.connection, "type"),
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
                prop.connection.properties["container"], (*loc, self.PropertyColumns.connection, "container")
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
            property_constraints = properties.constraints.get(container.container, {})
            require_constraints = self.read_container_constraints(container, row_no)
            if conflict := set(property_constraints.keys()).intersection(set(require_constraints.keys())):
                conflict_str = humanize_collection(conflict)
                location_str = self.source.location((self.Sheets.containers, row_no, self.ContainerColumns.constraint))
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {location_str} the container '{container.container!s}' has constraints defined "
                            f"with the same identifier(s) as the uniqueness constraint defined in the "
                            f"{self.Sheets.properties} sheet. Ensure that the identifiers are unique. "
                            f"Conflicting identifiers: {conflict_str}. "
                        )
                    )
                )
            constraints = {**property_constraints, **require_constraints}
            container_request = self._validate_obj(
                ContainerRequest,
                dict(
                    **self._create_container_ref(container.container),
                    usedFor=container.used_for,
                    name=container.name,
                    description=container.description,
                    properties=properties.container[container.container],
                    indexes=properties.indices.get(container.container),
                    constraints=constraints or None,
                ),
                (self.Sheets.containers, row_no),
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
                rows_str = humanize_collection([self.source.adjust_row_number(self.Sheets.containers, r) for r in rows])
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheets.containers,))} the values in "
                            f"column {self.ContainerColumns.container!r} must be unique. "
                            f"Duplicated entries for container '{entity!s}' found in rows {rows_str}."
                        )
                    )
                )
        return containers_requests

    def read_container_constraints(self, container: DMSContainer, row_no: int) -> dict[str, Constraint]:
        constraints: dict[str, Constraint] = {}
        if not container.constraint:
            return constraints
        for entity in container.constraint:
            loc = self.Sheets.containers, row_no, self.ContainerColumns.constraint
            if entity.prefix != "requires":
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location(loc)} the constraint '{entity.suffix}' on container "
                            f"'{container.container!s}' has an invalid type '{entity.prefix}'. Only 'requires' "
                            f"constraints are supported at the container level."
                        )
                    )
                )
                continue

            if "require" not in entity.properties:
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location(loc)} the constraint '{entity.suffix}' on container "
                            f"'{container.container!s}' is missing the "
                            f"'require' property which is required for container level constraints."
                        )
                    )
                )
                continue
            data = {
                "constraintType": entity.prefix,
                "require": self._create_container_ref_unparsed(entity.properties["require"], loc),
            }
            created = self._validate_adapter(ConstraintAdapter, data, loc)
            if created is None:
                continue
            constraints[entity.suffix] = created
        return constraints

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
                                f"In {self.source.location((self.Sheets.views, row_no, self.ViewColumns.filter))} "
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
                (self.Sheets.views, row_no),
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
                rows_str = humanize_collection([self.source.adjust_row_number(self.Sheets.views, r) for r in rows])
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"In {self.source.location((self.Sheets.views,))} the values in "
                            f"column {self.ViewColumns.view!r} must be unique. "
                            f"Duplicated entries for view '{entity!s}' found in rows {rows_str}."
                        )
                    )
                )
        return views_requests, set(rows_by_seen.keys())

    def read_data_model(self, tables: TableDMS, valid_view_entities: set[ParsedEntity]) -> DataModelRequest:
        data = {
            **{meta.key: meta.value for meta in tables.metadata},
            "views": [self._create_view_ref(view.view) for view in tables.views if view.view in valid_view_entities],
        }
        model = self._validate_obj(DataModelRequest, data, (self.Sheets.metadata,), field_name="value")
        if model is None:
            # This is the last step, so we can raise the error here.
            raise DataModelImportException(self.errors) from None
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
            missing_required_descriptor="empty" if field_name == "column" else "missing",
        ):
            if message in seen:
                continue
            seen.add(message)
            self.errors.append(ModelSyntaxError(message=message))
