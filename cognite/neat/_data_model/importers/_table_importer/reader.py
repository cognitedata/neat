import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cognite.neat._data_model.models.dms import (
    Constraint,
    ContainerPropertyDefinition,
    ContainerRequest,
    DataModelRequest,
    Index,
    RequestSchema,
    SpaceRequest,
    ViewCorePropertyRequest,
    ViewRequest,
    ViewRequestProperty,
)
from cognite.neat._data_model.models.entities import ParsedEntity
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import DMSContainer, DMSProperty, DMSView, TableDMS
from .source import TableSource

T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)


@dataclass
class ReadProperties:
    container: dict[ParsedEntity, dict[str, ContainerPropertyDefinition]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    view: dict[ParsedEntity, dict[str, ViewRequestProperty]] = field(default_factory=lambda: defaultdict(dict))
    indices: dict[ParsedEntity, dict[str, Index]] = field(default_factory=dict)
    constraints: dict[ParsedEntity, dict[str, Constraint]] = field(default_factory=dict)


class DMSTableReader:
    def __init__(self, default_space: str, default_version: str, source: TableSource) -> None:
        self.default_space = default_space
        self.default_version = default_version
        self.source = source
        self.errors: list[ModelSyntaxError] = []

    def read_tables(self, tables: TableDMS) -> RequestSchema:
        space_request = self.read_space(self.default_space)
        properties = self.read_properties(tables.properties)
        containers = self.read_containers(tables.containers, properties)
        views = self.read_views(tables.views, properties.view)
        data_model = self.read_data_model(tables)

        if self.errors:
            raise ModelImportError(self.errors) from None
        return RequestSchema(dataModel=data_model, views=views, containers=containers, spaces=[space_request])

    def read_space(self, space: str) -> SpaceRequest:
        try:
            return SpaceRequest(space=space)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, lambda x: "In Metadata")]
            )
            # If space is invalid, we stop parsing to avoid raising an error for every place the space is used.
            raise ModelImportError(self.errors) from None

    def read_properties(self, properties: list[DMSProperty]) -> ReadProperties:
        parsed_properties = ReadProperties()
        indices: dict[ParsedEntity, list[tuple[str, ParsedEntity]]] = defaultdict(list)
        constraints: dict[ParsedEntity, list[tuple[str, ParsedEntity]]] = defaultdict(list)

        for row_no, prop in enumerate(properties):
            self._process_view_property(prop, parsed_properties)
            if prop.container is None:
                continue
            self._process_container_property(prop, parsed_properties, row_no)
            self._collect_indices_and_constraints(prop, indices, constraints, row_no)

        parsed_properties.indices = self.create_indices(indices)
        parsed_properties.constraints = self.create_constraints(constraints)
        return parsed_properties

    def _process_view_property(self, prop: DMSProperty, parsed_properties: ReadProperties) -> None:
        try:
            view_prop = self.read_view_property(prop)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self.source.location)]
            )
        else:
            parsed_properties.view[prop.view][prop.view_property] = view_prop

    def _process_container_property(self, prop: DMSProperty, parsed_properties: ReadProperties, row_no: int) -> None:
        try:
            container_prop = self.read_container_property(prop)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self.source.location)]
            )
            return None
        container_properties = parsed_properties.container[prop.container]
        existing_prop = container_properties.get(prop.container_property)

        if existing_prop is None:
            container_properties[prop.container_property] = container_prop
        else:
            self._validate_property_equality(existing_prop, container_prop, row_no)
        return None

    def _collect_indices_and_constraints(
        self,
        prop: DMSProperty,
        indices: dict[ParsedEntity, list[tuple[str, ParsedEntity]]],
        constraints: dict[ParsedEntity, list[tuple[str, ParsedEntity]]],
        row_no: int,
    ) -> None:
        if prop.index is not None and self._valid_index_syntax(row_no, prop.index):
            indices[prop.container].append((prop.container_property, prop.index))

        if prop.constraint is not None and self._valid_constraint_syntax(row_no, prop.constraint):
            constraints[prop.container].append((prop.container_property, prop.constraint))

    def _valid_index_syntax(self, row_no: int, index_list: list[ParsedEntity]) -> bool:
        # Todo
        return True

    def _valid_constraint_syntax(self, row_no: int, constraint_list: list[ParsedEntity]) -> bool:
        raise NotImplementedError()

    def read_view_property(self, prop: DMSProperty) -> ViewRequestProperty:
        """Reads a single view property from a given row in the properties table.

        The type of property (core, edge, reverse direct relation) is determined based on the connection column
        as follows:
        1. If the connection is empty or 'direct' it is a core property.
        2. If the connection is 'edge' it is an edge property.
        3. If the connection is 'reverse' it is a reverse direct relation property
        4. Otherwise, it is an error.

        Args:
            prop (DMSProperty): The property row to read.

        Returns:
            ViewRequestProperty: The parsed view property.
        """

        if prop.connection is None or prop.connection == "direct":
            return self.create_core_view_property(prop)
        elif prop.connection.suffix == "edge":
            return self.create_edge_view_property(prop)
        elif prop.connection.suffix == "reverse":
            return self.create_reverse_direct_relation_view_property(prop)
        else:
            raise ValueError()

    def create_core_view_property(self, prop: DMSProperty) -> ViewCorePropertyRequest:
        return ViewCorePropertyRequest(
            connectionType="primary_property",
            name=prop.container_property_name,
            description=prop.container_property_description,
            container=self._create_container_ref(prop.container),
            containerPropertyIdentifier=prop.container_property,
            source=None if prop.connection is None else self._create_view_ref(prop.connection),
        )

    def create_edge_view_property(
        self,
        prop: DMSProperty,
    ) -> ViewRequestProperty | None:
        # Implementation to read an edge view property from DMSProperty
        raise NotImplementedError()

    def create_reverse_direct_relation_view_property(
        self,
        prop: DMSProperty,
    ) -> ViewRequestProperty | None:
        # Implementation to read a reverse direct relation view property from DMSProperty
        raise NotImplementedError()

    def read_container_property(self, prop: DMSProperty) -> ContainerPropertyDefinition:
        data_type = self._read_data_type(prop)
        return ContainerPropertyDefinition(
            immutable=prop.immutable,
            nullable=prop.min_count == 0 or prop.min_count is None,
            auto_increment=prop.auto_increment,
            default_value=prop.default,
            description=prop.container_property_description,
            name=prop.container_property_name,
            type=data_type,
        )

    def _read_data_type(self, prop: DMSProperty) -> dict[str, Any]:
        # Implementation to read the container property type from DMSProperty
        is_list = None if prop.max_count is None else prop.max_count > 1
        max_list_size: int | None = None
        if is_list and prop.max_count is not None:
            max_list_size = prop.max_count

        args: dict[str, Any] = {
            "maxListSize": max_list_size,
            "list": is_list,
        }

        if prop.connection is None:
            args["type"] = prop.value_type.suffix
            args.update(prop.value_type.properties)
        else:
            args["type"] = "direct"
            if "container" in prop.connection.properties:
                args["container"] = self._create_container_ref(prop.connection.properties["container"])
        return args

    def read_index(self, row_no: int, index_str: str | None) -> ParsedEntity | None:
        raise NotImplementedError()

    def read_constraint(self, row_no: int, constraint_str: str | None) -> ParsedEntity | None:
        raise NotImplementedError()

    def _validate_property_equality(
        self, existing_prop: ContainerPropertyDefinition, new_prop: ContainerPropertyDefinition, row_no: int
    ) -> None:
        # Implementation to validate equality of two container properties
        raise NotImplementedError()

    def create_indices(
        self, index_list: dict[ParsedEntity, list[tuple[str, ParsedEntity]]]
    ) -> dict[ParsedEntity, dict[str, Index]]:
        raise NotImplementedError()

    def create_constraints(
        self, constraints: dict[ParsedEntity, list[tuple[str, ParsedEntity]]]
    ) -> dict[ParsedEntity, dict[str, Constraint]]:
        raise NotImplementedError()

    def read_containers(self, containers: list[DMSContainer], properties: ReadProperties) -> list[ContainerRequest]:
        # Implementation to read containers from DMSContainer list
        containers_requests: list[ContainerRequest] = []
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
                row_no,
                TableDMS.model_fields["containers"].validation_alias,
            )
            if container_request is None:
                continue
            containers_requests.append(container_request)
        return containers_requests

    def read_views(
        self,
        views: list[DMSView],
        properties: dict[ParsedEntity, dict[str, ViewRequestProperty]],
    ) -> list[ViewRequest]:
        views_requests: list[ViewRequest] = []
        for row_no, view in enumerate(views):
            filter_dict: dict[str, Any] | None = None
            if view.filter is not None:
                try:
                    filter_dict = json.loads(view.filter)
                except ValueError as e:
                    self.errors.append(
                        ModelSyntaxError(
                            message=(
                                f"Invalid filter for view '{view.view}' in row {row_no + 1} of the views table: {e}"
                            )
                        )
                    )
                    continue
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
                row_no,
                TableDMS.model_fields["views"].validation_alias,
            )
            if view_request is None:
                continue
            views_requests.append(view_request)
        return views_requests

    def read_data_model(self, tables: TableDMS) -> DataModelRequest:
        try:
            return DataModelRequest.model_validate(
                {
                    **{meta.name: meta.value for meta in tables.metadata},
                    "views": [self._create_view_ref(view.view) for view in tables.views if view.in_model is not False],
                }
            )
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, lambda x: "In Metadata")]
            )
            raise ModelImportError(self.errors) from None

    def _create_view_ref(self, entity: ParsedEntity) -> dict[str, str | None]:
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

    def _create_container_ref(self, entity: ParsedEntity) -> dict[str, str]:
        return {
            "space": entity.prefix or self.default_space,
            "externalId": entity.suffix,
        }

    def _validate_obj(self, obj: type[T_BaseModel], data: dict, row_no: int, table_name: str) -> T_BaseModel | None:
        try:
            return obj.model_validate(data)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self.source.location)]
            )
            return None
