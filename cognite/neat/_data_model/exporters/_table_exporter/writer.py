import json
from dataclasses import dataclass, field

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
    ContainerRequest,
    DataModelRequest,
    RequestSchema,
    ViewReference,
    ViewRequest,
)
from cognite.neat._data_model.models.entities import ParsedEntity


@dataclass
class WrittenProperties:
    properties: list[DMSProperty] = field(default_factory=list)
    enum_collections: list[DMSEnum] = field(default_factory=list)
    nodes: list[DMSNode] = field(default_factory=list)


class DMSTableWriter:
    def __init__(self, default_space: str, default_version: str) -> None:
        self.default_space = default_space
        self.default_version = default_version

    def write_tables(self, schema: RequestSchema) -> TableDMS:
        metadata = self.write_metadata(schema.data_model)
        properties = self.write_properties(schema)
        views = self.write_views(schema.views, set(schema.data_model.views))
        containers = self.write_containers(schema.containers)

        return TableDMS(
            metadata=metadata,
            properties=properties.properties,
            views=views,
            containers=containers,
            enum=properties.enum_collections,
            nodes=properties.nodes,
        )

    def write_metadata(self, data_model: DataModelRequest) -> list[MetadataValue]:
        return [
            MetadataValue(key=key, value=value)
            for key, value in data_model.model_dump(mode="json", by_alias=True, exclude_none=True, exclude={"views"})
        ]

    def write_properties(self, schema: RequestSchema) -> WrittenProperties:
        output = WrittenProperties()
        for view in schema.views:
            if not view.properties:
                continue
            for prop in view.properties:
                parsed_prop = DMSProperty(
                    view=ParsedEntity(prefix=view.space, suffix=view.external_id, properties={"version": view.version}),
                    property=ParsedEntity(
                        prefix=prop.space, suffix=prop.external_id, properties={"version": prop.version}
                    ),
                    name=prop.name,
                    description=prop.description,
                    data_type=prop.data_type,
                    unit=prop.unit,
                    is_key=prop.is_key,
                    is_required=prop.is_required,
                    is_unique=prop.is_unique,
                    default_value=prop.default_value,
                    allowed_values=json.dumps(prop.allowed_values) if prop.allowed_values else None,
                )
                output.properties.append(parsed_prop)

                if prop.allowed_values:
                    for value in prop.allowed_values:
                        enum = DMSEnum(
                            collection=f"{view.space}:{view.external_id}:{prop.external_id}",
                            value=value,
                            name=None,
                            description=None,
                        )
                        output.enum_collections.append(enum)

                if prop.data_type == "node" and prop.node:
                    node = DMSNode(
                        node=ParsedEntity(
                            prefix=prop.node.space,
                            suffix=prop.node.external_id,
                            properties={"version": prop.node.version},
                        )
                    )
                    output.nodes.append(node)
        return output

    def write_views(self, views: list[ViewRequest], model_views: set[ViewReference]) -> list[DMSView]:
        return [
            DMSView(
                view=ParsedEntity(prefix=view.space, suffix=view.external_id, properties={"version": view.version}),
                name=view.name,
                description=view.description,
                implements=list[ParsedEntity],
                filter=json.dumps(view.filter) if view.filter else None,
                in_model=view.as_reference() in model_views,
            )
            for view in views
        ]

    def write_containers(self, containers: list[ContainerRequest]) -> list[DMSContainer]:
        return [
            DMSContainer(
                container=ParsedEntity(),
                name=container.name,
                description=container.description,
                constraint=[
                    ParsedEntity(prefix=constraint.constraint_type, suffix=constraint_id, properties=...)
                    for constraint_id, constraint in container.constraints.items()
                ]
                if container.constraints
                else None,
                used_for=container.used_for,
            )
            for container in containers
        ]
