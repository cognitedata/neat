import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cognite.neat._data_model.models.dms import (
    Constraint,
    ConstraintAdapter,
    ContainerPropertyDefinition,
    ContainerRequest,
    DataModelRequest,
    Index,
    IndexAdapter,
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
    def __init__(self, default_space: str, default_version: str, source: TableSource) -> None:
        self.default_space = default_space
        self.default_version = default_version
        self.source = source
        self.errors: list[ModelSyntaxError] = []

    def read_tables(self, tables: TableDMS) -> RequestSchema:
        space_request = self.read_space(self.default_space)
        read = self.read_properties(tables.properties)
        processed = self.process_properties(read)
        containers = self.read_containers(tables.containers, processed)
        views = self.read_views(tables.views, processed.view)
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
        read = ReadProperties()
        for row_no, prop in enumerate(properties):
            self._process_view_property(prop, read, row_no)
            if prop.container is None or prop.container_property is None:
                continue
            self._process_container_property(prop, read, row_no)
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
            if len(prop_list) > 1:
                raise NotImplementedError()

        return container_props

    def create_view_properties(self, read: ReadProperties) -> dict[ParsedEntity, dict[str, ViewRequestProperty]]:
        view_props: dict[ParsedEntity, dict[str, ViewRequestProperty]] = defaultdict(dict)
        for (view_entity, prop_id), prop_list in read.view.items():
            if len(prop_list) == 0:
                # Should not happen
                continue
            view_props[view_entity][prop_id] = prop_list[0].view_property
            if len(prop_list) > 1:
                raise NotImplementedError()

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
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"Index '{index_id}' on container '{container_entity}' is defined on multiple properties "
                            f"but some of them are missing the 'order' attribute (rows "
                            f"{', '.join(str(idx.row_no + 1) for idx in missing_order)} in the properties table)."
                        )
                    )
                )
                continue
            index.properties = [idx.prop_id for idx in sorted(index_list, key=lambda x: x.order)]
            indices[container_entity][index_id] = index
        return indices

    def create_constraints(self, read: ReadProperties) -> dict[ParsedEntity, dict[str, Constraint]]:
        constraints: dict[ParsedEntity, dict[str, Constraint]] = defaultdict(dict)
        for (container_entity, constraint_id), constraint_list in read.constraints.items():
            raise NotImplementedError()
        return constraints

    def _process_view_property(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        try:
            view_prop = self.read_view_property(prop)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self.source.location)]
            )
        else:
            read.view[(prop.view, prop.container_property)].append(
                ReadViewProperty(prop.container_property, row_no, view_prop)
            )

    def _process_container_property(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        try:
            container_prop = self.read_container_property(prop)
        except ValidationError as e:
            self.errors.extend(
                [ModelSyntaxError(message=message) for message in humanize_validation_error(e, self.source.location)]
            )
            return None
        read.container[(prop.container, prop.container_property)].append(
            ReadContainerProperty(prop.container_property, row_no, container_prop)
        )

    def _process_index(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        if prop.index is None:
            return
        for index in prop.index:
            try:
                created = self.read_index(index, prop.container_property, row_no)
            except ValidationError as e:
                self.errors.extend(
                    [
                        ModelSyntaxError(message=message)
                        for message in humanize_validation_error(e, self.source.location)
                    ]
                )
                return
            except ValueError as e:
                self.errors.append(ModelSyntaxError(message=str(e)))
                return
            read.indices[(prop.container, index.suffix)].append(created)

    @staticmethod
    def read_index(index: ParsedEntity, prop_id: str, row_no: int) -> ReadIndex:
        return ReadIndex(
            prop_id=prop_id,
            order=int(index.properties["order"]) if "order" in index.properties else None,
            row_no=row_no,
            index_id=index.suffix,
            index=IndexAdapter.validate_python(
                {
                    "indexType": index.prefix,
                    "properties": [prop_id],
                    **index.properties,
                }
            ),
        )

    def _process_constraint(self, prop: DMSProperty, read: ReadProperties, row_no: int) -> None:
        if prop.constraint is None:
            return
        for constraint in prop.constraint:
            try:
                created = self.read_constraint(constraint, prop.container_property, row_no)
            except ValidationError as e:
                self.errors.extend(
                    [
                        ModelSyntaxError(message=message)
                        for message in humanize_validation_error(e, self.source.location)
                    ]
                )
                return
            except ValueError as e:
                self.errors.append(ModelSyntaxError(message=str(e)))
                return
            read.constraints[(prop.container, constraint.suffix)].append(created)

    @staticmethod
    def read_constraint(constraint: ParsedEntity, prop_id: str, row_no: int) -> ReadConstraint:
        return ReadConstraint(
            prop_id=prop_id,
            order=int(constraint.properties["order"]) if "order" in constraint.properties else None,
            constraint_id=constraint.suffix,
            row_no=row_no,
            constraint=ConstraintAdapter.validate_python(
                {"constraintType": constraint.prefix, "properties": [prop_id], **constraint.properties}
            ),
        )

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
            return self.read_core_view_property(prop)
        elif prop.connection.suffix == "edge":
            return self.read_edge_view_property(prop)
        elif prop.connection.suffix == "reverse":
            return self.read_reverse_direct_relation_view_property(prop)
        else:
            raise ValueError()

    def read_core_view_property(self, prop: DMSProperty) -> ViewCorePropertyRequest:
        return ViewCorePropertyRequest(
            connectionType="primary_property",
            name=prop.container_property_name,
            description=prop.container_property_description,
            container=self._create_container_ref(prop.container),
            containerPropertyIdentifier=prop.container_property,
            source=None if prop.connection is None else self._create_view_ref(prop.connection),
        )

    def read_edge_view_property(
        self,
        prop: DMSProperty,
    ) -> ViewRequestProperty | None:
        # Implementation to read an edge view property from DMSProperty
        raise NotImplementedError()

    def read_reverse_direct_relation_view_property(
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
                row_no,
                TableDMS.model_fields["containers"].validation_alias,
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
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"Duplicate container '{entity}' found in rows "
                            f"{', '.join(str(r + 1) for r in rows)} of the containers table."
                        )
                    )
                )
        return containers_requests

    def read_views(
        self,
        views: list[DMSView],
        properties: dict[ParsedEntity, dict[str, ViewRequestProperty]],
    ) -> list[ViewRequest]:
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
            if view.view in rows_by_seen:
                rows_by_seen[view.view].append(row_no)
            else:
                views_requests.append(view_request)
                rows_by_seen[view.view] = [row_no]
        for entity, rows in rows_by_seen.items():
            if len(rows) > 1:
                self.errors.append(
                    ModelSyntaxError(
                        message=(
                            f"Duplicate view '{entity!s}' found in rows "
                            f"{', '.join(str(r + 1) for r in rows)} of the views table."
                        )
                    )
                )
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
