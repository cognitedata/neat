from dataclasses import dataclass

from cognite.neat._data_model.importers._table_importer.data_classes import (
    DMSContainer,
    DMSEnum,
    DMSNode,
    DMSProperty,
    DMSView,
    MetadataValue,
    TableDMS,
)
from cognite.neat._data_model.models.dms import ContainerRequest, DataModelRequest, RequestSchema, ViewRequest


@dataclass
class WrittenProperties:
    properties: list[DMSProperty]
    enum_collections: list[DMSEnum]
    nodes: list[DMSNode]


class DMSTableWriter:
    def __init__(self, default_space: str, default_version: str) -> None:
        self.default_space = default_space
        self.default_version = default_version

    def write_tables(self, schema: RequestSchema) -> TableDMS:
        metadata = self.write_metadata(schema.data_model)
        properties = self.write_properties(schema)
        views = self.write_views(schema.views)
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
        raise NotImplementedError()

    def write_properties(self, schema: RequestSchema) -> WrittenProperties:
        raise NotImplementedError()

    def write_views(self, views: list[ViewRequest]) -> list[DMSView]:
        raise NotImplementedError()

    def write_containers(self, containers: list[ContainerRequest]) -> list[DMSContainer]:
        raise NotImplementedError()
