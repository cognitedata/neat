import json
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    DATA_TYPE_CLS_BY_TYPE,
    Constraint,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    DataType,
    DirectNodeRelation,
    Index,
    RequestSchema,
    SpaceRequest,
    ViewCorePropertyRequest,
    ViewReference,
    ViewRequest,
    ViewRequestProperty,
)
from cognite.neat._data_model.models.entities import ParsedEntity, parse_entity
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import CellValue
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import DMSContainer, DMSProperty, DMSView, TableDMS


@dataclass
class ViewProperty:
    reference: ViewReference
    property: ViewRequestProperty
    prop_id: str


@dataclass
class ContainerProperty:
    reference: ContainerReference
    property: ContainerPropertyDefinition
    prop_id: str


@dataclass
class Properties:
    container: dict[ContainerReference, dict[str, ContainerPropertyDefinition]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    view: dict[ViewReference, dict[str, ViewRequestProperty]] = field(default_factory=lambda: defaultdict(dict))
    indices: dict[ContainerReference, dict[str, Index]] = field(default_factory=dict)
    constraints: dict[ContainerReference, dict[str, Constraint]] = field(default_factory=dict)


@dataclass
class SpreadsheetRead:
    """This class is used to store information about the source spreadsheet.

    It is used to adjust row numbers to account for header rows and empty rows
    such that the error/warning messages are accurate.
    """

    header_row: int = 1
    empty_rows: list[int] = field(default_factory=list)
    skipped_rows: list[int] = field(default_factory=list)
    is_one_indexed: bool = True

    def __post_init__(self) -> None:
        self.empty_rows = sorted(self.empty_rows)

    def adjusted_row_number(self, row_no: int) -> int:
        output = row_no
        for empty_row in self.empty_rows:
            if empty_row <= output:
                output += 1
            else:
                break

        for skipped_rows in self.skipped_rows:
            if skipped_rows <= output:
                output += 1
            else:
                break

        return output + self.header_row + (1 if self.is_one_indexed else 0)


@dataclass
class TableSource:
    source: str
    table_read: dict[str, SpreadsheetRead] = field(default_factory=dict)


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]], source: TableSource | None = None) -> None:
        self._table = tables
        self._source = source or TableSource("Unknown")
        self._errors: list[ModelSyntaxError] = []

    def to_data_model(self) -> RequestSchema:
        table = self._read_tables()

        metadata_kv = {meta.name: meta.value for meta in table.metadata}
        space, version = self._read_defaults(metadata_kv)
        space_request = self._read_space(space)

        properties = self._read_properties(table.properties, space, version)
        containers = self._read_containers(table.containers, space, properties)
        views = self._read_views(table.views, space, version, properties.view)

        data_model = self._read_data_model(
            metadata_kv,
            [
                view.as_reference()
                for view, table in zip(views, table.views, strict=False)
                if table.in_model is not False
            ],
        )
        if self._errors:
            raise ModelImportError(self._errors) from None

        return RequestSchema(dataModel=data_model, views=views, containers=containers, spaces=[space_request])

    def _read_tables(self) -> TableDMS:
        try:
            # Check tables, columns, and entity syntax.
            table = TableDMS.model_validate(self._table)
        except ValidationError as e:
            self._errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self._location_source)]
            )
            raise ModelImportError(self._errors) from None

        unused_tables = set(self._table.keys()) - {
            field_.validation_alias or table_id for table_id, field_ in TableDMS.model_fields.items()
        }
        if unused_tables:
            # Todo: Consider making this a warning instead or silently ignoring it.
            self._errors.append(
                ModelSyntaxError(
                    message=f"{self._location_source((0,))} unused tables found: {humanize_collection(unused_tables)}"
                )
            )
        return table

    def _read_defaults(self, metadata_kv: dict[str, CellValue]) -> tuple[str, str]:
        default_space, default_version = metadata_kv.get("space"), metadata_kv.get("version")
        if default_space is None or default_version is None:
            missing = {"space" if default_space is None else "", "version" if default_version is None else ""}
            self._errors.append(
                ModelSyntaxError(
                    message=f"{self._location_metadata((0,))} missing required fields: {humanize_collection(missing)}"
                )
            )
            # If space or version is missing, we cannot continue parsing the model as these are used as defaults.
            raise ModelImportError(self._errors) from None
        return str(default_space), str(default_version)

    def _read_space(self, space: str) -> SpaceRequest:
        try:
            return SpaceRequest(space=space)
        except ValidationError as e:
            self._errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self._location_metadata)]
            )
            # If space is invalid, we stop parsing to avoid raising an error for every place the space is used.
            raise ModelImportError(self._errors) from None

    def _read_properties(
        self,
        properties: list[DMSProperty],
        default_space: str,
        default_version: str,
    ) -> Properties:
        parsed_properties = Properties()
        indices: dict[ContainerReference, list[tuple[str, ParsedEntity]]] = defaultdict(list)
        constraints: dict[ContainerReference, list[tuple[str, ParsedEntity]]] = defaultdict(list)
        for row_no, prop in enumerate(properties):
            view = self._read_view_property(row_no, prop, default_space, default_version)
            if view is not None:
                # If view is None there was an error in parsing the view property,
                # and the error has already been recorded.
                parsed_properties.view[view.reference][view.prop_id] = view.property

            container = self._read_container_property(row_no, prop, default_space)
            if container is None:
                # Connection property or error in parsing container property, and the error has already been recorded.
                continue
            index = self._read_index(row_no, prop.index)
            if index is not None:
                indices[container.reference].append((container.prop_id, index))
            constraint = self._read_constraint(row_no, prop.constraint)
            if constraint is not None:
                constraints[container.reference].append((container.prop_id, constraint))

            container_properties = parsed_properties.container[container.reference]
            if container.prop_id not in container_properties:
                container_properties[container.prop_id] = container.property
                continue
            existing_prop = container_properties[container.prop_id]
            self._validate_property_equality(existing_prop, container.property, row_no)

        parsed_properties.indices = self._parse_indices(indices)
        parsed_properties.constraints = self._parse_constraints(constraints)

        return parsed_properties

    def _read_view_property(
        self, prop_no: int, prop: DMSProperty, default_space: str, default_version: str
    ) -> ViewProperty | None:
        """Reads a single view property from a given row in the properties table.

        The type of property (core, edge, reverse direct relation) is determined based on the connection column
        as follows:
        1. If the connection is empty or 'direct' it is a core property.
        2. If the connection is 'edge' it is an edge property.
        3. If the connection is 'reverse' it is a reverse direct relation property
        4. Otherwise, it is an error.

        Args:
            prop (DMSProperty): The property row to read.
            default_space (str): The default space to use if not specified in the property.
            default_version (str): The default version to use if not specified in the property.

        Returns:
            ViewProperty: The parsed view property.

        """
        view_entity = self._parse_entity(
            prop.view,
            default_space,
            default_version,
        )
        if view_entity is None:
            return None
        view_ref = ViewReference.model_construct(
            space=view_entity.prefix, externalId=view_entity.suffix, version=view_entity.properties.get("version")
        )
        connection_entity: ParsedEntity | None = None
        if prop.connection is not None:
            connection_entity = self._parse_entity(prop.connection)
            if connection_entity is None:
                return None

        if connection_entity is None or connection_entity.suffix == "direct":
            request_prop = self._read_core_view_property(prop, connection_entity, default_space)
        elif connection_entity.suffix == "edge":
            request_prop = self._read_edge_view_property(prop, connection_entity)
        elif connection_entity.suffix == "reverse":
            request_prop = self._read_reverse_direct_relation_view_property(prop, connection_entity)
        else:
            self._errors.append(
                ModelSyntaxError(
                    message=(
                        f"Invalid connection type '{connection_entity.suffix}' for property '{prop.view_property}' "
                        f"in view '{prop.view}'. Must be one of 'direct', 'edge', 'reverse' or empty."
                    )
                )
            )
            return None
        return ViewProperty(view_ref, request_prop, prop.view_property) if request_prop is not None else None

    def _read_core_view_property(
        self,
        prop: DMSProperty,
        connection_entity: ParsedEntity | None,
        default_space: str,
    ) -> ViewCorePropertyRequest | None:
        parsed_container = self._parse_entity(prop.container, default_space)
        if parsed_container is None:
            return None
        return ViewCorePropertyRequest.model_validate(
            dict(
                connection_type="primary_property",
                name=prop.container_property_name,
                description=prop.container_property_description,
                container={
                    "space": parsed_container.prefix,
                    "externalId": parsed_container.suffix,
                },
                container_property_identifier=prop.container_property,
                source=None
                if connection_entity is None
                else {
                    "space": connection_entity.prefix,
                    "externalId": connection_entity.suffix,
                    "version": connection_entity.properties.get("version"),
                },
            )
        )

    def _read_edge_view_property(
        self,
        prop: DMSProperty,
        connection_entity: ParsedEntity,
    ) -> ViewProperty | None:
        # Implementation to read an edge view property from DMSProperty
        raise NotImplementedError()

    def _read_reverse_direct_relation_view_property(
        self,
        prop: DMSProperty,
        connection_entity: ParsedEntity,
    ) -> ViewProperty | None:
        # Implementation to read a reverse direct relation view property from DMSProperty
        raise NotImplementedError()

    def _read_container_property(self, prop_id: int, prop: DMSProperty, default_space: str) -> ContainerProperty | None:
        # Implementation to read a single container property from DMSProperty
        parsed_container = self._parse_entity(prop.container, default_space)
        if parsed_container is None:
            return None
        container_ref = ContainerReference.model_construct(
            space=parsed_container.prefix, external_id=parsed_container.suffix
        )

        container_type = self._read_container_type(prop, default_space)
        if container_type is None:
            return None

        return ContainerProperty(
            container_ref,
            ContainerPropertyDefinition(
                immutable=prop.immutable,
                nullable=prop.min_count == 0 or prop.min_count is None,
                auto_increment=prop.auto_increment,
                default_value=prop.default,
                description=prop.container_property_description,
                name=prop.container_property_name,
                type=container_type,
            ),
            prop.container_property,
        )

    def _read_container_type(self, prop: DMSProperty, default_space: str) -> DataType | None:
        # Implementation to read the container property type from DMSProperty
        is_list = None if prop.max_count is None else prop.max_count > 1
        max_list_size: int | None = None
        if is_list and prop.max_count is not None:
            max_list_size = prop.max_count

        args: dict[str, CellValue] = {
            "maxListSize": max_list_size,
            "list": is_list,
        }

        if prop.connection is None:
            parsed_value_type = self._parse_entity(prop.value_type)
            if parsed_value_type is None:
                return None
            type_ = parsed_value_type.suffix
            if type_ not in DATA_TYPE_CLS_BY_TYPE:
                self._errors.append(
                    ModelSyntaxError(
                        message=(
                            f"Invalid data type '{type_}' for property '{prop.container_property}' "
                            f"in container '{prop.container}'."
                        )
                    )
                )
                return None
            cls_ = DATA_TYPE_CLS_BY_TYPE[type_]
            args.update(parsed_value_type.properties)
            return cls_(**args)
        else:
            parsed_connection = parse_entity(prop.connection)
            if parsed_connection is None:
                return None
            if "container" in parsed_connection.properties:
                container = self._parse_entity(parsed_connection.properties["container"], default_space)
                args["container"] = {"space": container.prefix, "externalId": container.suffix}
            return DirectNodeRelation(**args)

    def _read_index(self, row_no: int, index_str: str | None) -> ParsedEntity | None:
        raise NotImplementedError()

    def _read_constraint(self, row_no: int, constraint_str: str | None) -> ParsedEntity | None:
        raise NotImplementedError()

    def _validate_property_equality(
        self, existing_prop: ContainerPropertyDefinition, new_prop: ContainerPropertyDefinition, row_no: int
    ) -> None:
        # Implementation to validate equality of two container properties
        raise NotImplementedError()

    def _parse_indices(
        self, indices: dict[ContainerReference, list[tuple[str, ParsedEntity]]]
    ) -> dict[ContainerReference, dict[str, Index]]:
        result: dict[ContainerReference, dict[str, Index]] = {}
        for container_ref, index_list in indices.items():
            created_indices = self._create_indices(index_list)
            if created_indices is not None:
                result[container_ref] = created_indices
        return result

    def _create_indices(self, index_list: list[tuple[str, ParsedEntity]]) -> dict[str, Index]:
        raise NotImplementedError()

    def _parse_constraints(
        self, constraints: dict[ContainerReference, list[tuple[str, ParsedEntity]]]
    ) -> dict[ContainerReference, dict[str, Constraint]]:
        raise NotImplementedError()

    def _read_containers(
        self,
        containers: list[DMSContainer],
        default_space: str,
        properties: Properties,
    ) -> list[ContainerRequest]:
        # Implementation to read containers from DMSContainer list
        containers_requests: list[ContainerRequest] = []
        for row_no, container in enumerate(containers):
            parsed_container = self._parse_entity(container.container, default_space)
            if parsed_container is None:
                continue
            container_ref = ContainerReference.model_construct(
                space=parsed_container.prefix, external_id=parsed_container.suffix
            )
            if container_ref not in properties:
                self._errors.append(
                    ModelSyntaxError(
                        message=(
                            f"No properties defined for container '{container.container}' "
                            f"in row {row_no + 1} of the containers table."
                        )
                    )
                )
                continue
            container_request = ContainerRequest.model_construct(
                space=container_ref.space,
                external_id=container_ref.external_id,
                used_for=container.used_for,
                description=container.description,
                properties=properties.container[container_ref],
                indexes=properties.indices.get(container_ref),
                constraints=properties.constraints.get(container_ref),
            )
            containers_requests.append(container_request)
        return containers_requests

    def _read_views(
        self,
        views: list[DMSView],
        default_space: str,
        default_version: str,
        properties: dict[ViewReference, dict[str, ViewRequestProperty]],
    ) -> list[ViewRequest]:
        views_requests: list[ViewRequest] = []
        for row_no, view in enumerate(views):
            parsed_view = self._parse_entity(view.view, default_space, default_version)
            if parsed_view is None:
                continue
            view_ref = ViewReference.model_construct(
                space=parsed_view.prefix,
                external_id=parsed_view.suffix,
                version=parsed_view.properties.get("version"),
            )
            if view_ref not in properties:
                self._errors.append(
                    ModelSyntaxError(
                        message=(
                            f"No properties defined for view '{view.view}' in row {row_no + 1} of the views table."
                        )
                    )
                )
                continue
            implements: list[ViewReference] | None = None
            if view.implements is not None:
                implements = []
                for impl in view.implements.split(","):
                    impl_entity = self._parse_entity(impl.strip(), default_space, default_version)
                    if impl_entity is None:
                        continue
                    implements.append(
                        ViewReference.model_construct(
                            space=impl_entity.prefix,
                            external_id=impl_entity.suffix,
                            version=impl_entity.properties.get("version"),
                        )
                    )
            filter_dict = None
            if view.filter is not None:
                try:
                    filter_dict = json.loads(view.filter)
                except ValueError as e:
                    self._errors.append(
                        ModelSyntaxError(
                            message=(
                                f"Invalid filter for view '{view.view}' in row {row_no + 1} of the views table: {e}"
                            )
                        )
                    )
                    continue

            view_request = ViewRequest.model_construct(
                space=view_ref.space,
                external_id=view_ref.external_id,
                version=view_ref.version,
                name=view.name,
                description=view.description,
                implements=implements,
                filter=filter_dict,
                properties=properties[view_ref],
            )
            views_requests.append(view_request)
        return views_requests

    def _read_data_model(self, metadata: dict[str, CellValue], views: list[ViewReference]) -> DataModelRequest:
        try:
            return DataModelRequest(**metadata, views=views)
        except ValidationError as e:
            self._errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, lambda x: "In Metadata")]
            )
            raise ModelImportError(self._errors) from None

    def _parse_entity(
        self,
        entity_str: str,
        default_prefix: str | None = None,
        default_version: str | None = None,
        location: str | None = None,
    ) -> ParsedEntity | None:
        try:
            entity = parse_entity(entity_str)
        except ValueError as e:
            message = f"Error parsing: {e!s}"
            if location is not None:
                message = f"In {location} e{message[1:]}"
            self._errors.append(ModelSyntaxError(message=message))
            return None
        if default_prefix is None:
            return entity
        if entity.prefix == "":
            entity.prefix = default_prefix
            if default_version is not None and "version" not in entity.properties:
                entity.properties["version"] = default_version
        return entity

    def _location_table(self, json_path: tuple[str | int, ...]) -> str:
        if not json_path:
            return ""
        table_name = json_path[0]
        read = self._source.table_read.get(table_name)
        if read is None:
            return ""
        if len(json_path) < 2 or not isinstance(json_path[1], int):
            return f"In table '{table_name}'"
        row_no = json_path[1]
        adjusted_row_no = read.adjusted_row_number(row_no)
        return f"In table '{table_name}', row {adjusted_row_no} "

    @staticmethod
    def _location_metadata(json_path: tuple[str | int, ...]) -> str:
        return "In Metadata"

    def _location_source(self, json_path: tuple[str | int, ...]) -> str:
        return f"In source {self._source.source!r}"
