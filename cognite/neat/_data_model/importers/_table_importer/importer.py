from collections import defaultdict
from dataclasses import dataclass

from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    DATA_TYPE_CLS_BY_TYPE,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    DataType,
    DirectNodeRelation,
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


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]]) -> None:
        self._table = tables
        self._errors: list[ModelSyntaxError] = []

    def to_data_model(self) -> RequestSchema:
        table = self._read_tables()

        metadata_kv = {meta.name: meta.value for meta in table.metadata}
        default_space, default_version = metadata_kv.get("space"), metadata_kv.get("version")
        if default_space is None or default_version is None:
            missing = {"space" if default_space is None else "", "version" if default_version is None else ""}
            self._errors.append(
                ModelSyntaxError(message=f"Missing required metadata fields: {humanize_collection(missing)}")
            )
            raise ModelImportError(self._errors) from None

        space, version = str(default_space), str(default_version)
        container_properties, view_properties = self._read_properties(table.properties, space, version)

        containers = self._read_containers(table.containers, space, container_properties)
        views = self._read_views(table.views, space, version, view_properties)

        data_model = self._read_data_model(
            metadata_kv,
            [
                {
                    "space": view.space,
                    "externalId": view.external_id,
                    "version": view.version,
                }
                for view, table in zip(views, table.views, strict=False)
                if table.in_model is not False
            ],
        )
        if self._errors:
            raise ModelImportError(self._errors) from None

        try:
            return RequestSchema.model_validate(
                {
                    "dataModel": data_model.model_dump(exclude_unset=True, by_alias=True),
                    "views": [view.model_dump(by_alias=True) for view in views],
                    "containers": [container.model_dump(by_alias=True) for container in containers],
                    "spaces": [SpaceRequest(space=space).model_dump(by_alias=True)],
                }
            )
        except ValidationError as e:
            self._errors.extend([ModelSyntaxError(message=message) for message in humanize_validation_error(e)])
            raise ModelImportError(self._errors) from None

    def _read_tables(self) -> TableDMS:
        try:
            # Check tables and columns are correct.
            table = TableDMS.model_validate(self._table)
        except ValidationError as e:
            self._errors.extend([ModelSyntaxError(message=message) for message in humanize_validation_error(e)])
            raise ModelImportError(self._errors) from None
        unused_tables = set(self._table.keys()) - {
            field_.validation_alias or table_id for table_id, field_ in TableDMS.model_fields.items()
        }
        if unused_tables:
            self._errors.append(ModelSyntaxError(message=f"Unused tables found: {humanize_collection(unused_tables)}"))
        return table

    def _read_properties(
        self,
        properties: list[DMSProperty],
        default_space: str,
        default_version: str,
    ) -> tuple[
        dict[ContainerReference, dict[str, ContainerPropertyDefinition]],
        dict[ViewReference, dict[str, ViewRequestProperty]],
    ]:
        all_container_properties: dict[ContainerReference, dict[str, ContainerPropertyDefinition]] = defaultdict(dict)
        all_view_properties: dict[ViewReference, dict[str, ViewRequestProperty]] = defaultdict(dict)
        for row_no, prop in enumerate(properties):
            view = self._read_view_property(prop, default_space, default_version)
            if view is not None:
                # If view is None there was an error in parsing the view property,
                # and the error has already been recorded.
                all_view_properties[view.reference][view.prop_id] = view.property

            container = self._read_container_property(prop, default_space)
            if container is None:
                # Connection property or error in parsing container property, and the error has already been recorded.
                continue

            container_properties = all_container_properties[container.reference]
            if container.prop_id not in container_properties:
                container_properties[container.prop_id] = container.property
                continue
            existing_prop = container_properties[container.prop_id]
            self._validate_property_equality(existing_prop, container.property, row_no)

        return all_container_properties, all_view_properties

    def _read_view_property(self, prop: DMSProperty, default_space: str, default_version: str) -> ViewProperty | None:
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
        view_entity = self._parse_entity(prop.view, default_space, default_version)
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
        return ViewCorePropertyRequest.model_construct(
            connection_type="primary_property",
            name=prop.container_property_name,
            description=prop.container_property_description,
            container=ContainerReference.model_construct(
                space=parsed_container.prefix, external_id=parsed_container.suffix
            ),
            container_property_identifier=prop.container_property,
            source=None if connection_entity is None else ViewReference.model_construct(),
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

    def _read_container_property(self, prop: DMSProperty, default_space: str) -> ContainerProperty | None:
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
        args: dict[str, CellValue] = {
            "maxListSize": prop.max_count,
            "list": None if prop.max_count is None else prop.max_count > 1,
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
            return cls_.model_construct(**args)
        else:
            parsed_connection = parse_entity(prop.connection)
            if parsed_connection is None:
                return None
            if "container" in parsed_connection.properties:
                container = self._parse_entity(parsed_connection.properties["container"], default_space)
                args["container"] = {"space": container.prefix, "externalId": container.suffix}
            return DirectNodeRelation.model_construct(**args)

    def _validate_property_equality(
        self, existing_prop: ContainerPropertyDefinition, new_prop: ContainerPropertyDefinition, row_no: int
    ) -> None:
        # Implementation to validate equality of two container properties
        raise NotImplementedError()

    def _read_containers(
        self,
        containers: list[DMSContainer],
        default_space: str,
        properties: dict[ContainerReference, dict[str, ContainerPropertyDefinition]],
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
                properties=properties[container_ref],
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
                    filter_dict = eval(view.filter)  # nosec
                    if not isinstance(filter_dict, dict):
                        raise ValueError("Filter must evaluate to a dictionary.")
                except Exception as e:
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

    @staticmethod
    def _read_data_model(metadata: dict[str, CellValue], views: list[dict]) -> DataModelRequest:
        return DataModelRequest.model_construct(**metadata, views=views)  # type: ignore[arg-type]

    def _parse_entity(
        self, entity_str: str, default_prefix: str | None = None, default_version: str | None = None
    ) -> ParsedEntity | None:
        try:
            entity = parse_entity(entity_str)
        except ValueError as e:
            self._errors.append(ModelSyntaxError(message=str(e)))
            return None
        if default_prefix is None:
            return entity
        if entity.prefix == "":
            entity.prefix = default_prefix
            if default_version is not None and "version" not in entity.properties:
                entity.properties["version"] = default_version
        return entity
