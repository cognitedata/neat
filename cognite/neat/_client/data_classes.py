from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = Field(None, alias="nextCursor")


class ResourceLimit(BaseModel):
    """Model for resources with count and limit."""

    count: int
    limit: int


class InstancesDetail(BaseModel, populate_by_name=True):
    """Model for instances with detailed metrics."""

    edges: int
    soft_deleted_edges: int = Field(alias="softDeletedEdges")
    nodes: int
    soft_deleted_nodes: int = Field(alias="softDeletedNodes")
    instances: int
    instances_limit: int = Field(alias="instancesLimit")
    soft_deleted_instances: int = Field(alias="softDeletedInstances")
    soft_deleted_instances_limit: int = Field(alias="softDeletedInstancesLimit")


class StatisticsResponse(BaseModel, populate_by_name=True):
    """Main API response model."""

    spaces: ResourceLimit
    containers: ResourceLimit
    views: ResourceLimit
    data_models: ResourceLimit = Field(alias="dataModels")
    container_properties: ResourceLimit = Field(alias="containerProperties")
    instances: InstancesDetail
    concurrent_read_limit: int = Field(alias="concurrentReadLimit")
    concurrent_write_limit: int = Field(alias="concurrentWriteLimit")
    concurrent_delete_limit: int = Field(alias="concurrentDeleteLimit")


class SpaceStatisticsItem(BaseModel, populate_by_name=True):
    """Individual space statistics item."""

    space: str
    containers: int
    views: int
    data_models: int = Field(alias="dataModels")
    edges: int
    soft_deleted_edges: int = Field(alias="softDeletedEdges")
    nodes: int
    soft_deleted_nodes: int = Field(alias="softDeletedNodes")

    @property
    def is_empty(self) -> bool:
        """Check if the space has zero usage."""
        return (
            self.containers == 0 and self.views == 0 and self.data_models == 0 and self.edges == 0 and self.nodes == 0
        )


class SpaceStatisticsResponse(BaseModel, populate_by_name=True):
    """Response model for space statistics endpoint."""

    items: list[SpaceStatisticsItem]

    def empty_spaces(self) -> list[str]:
        """Get a list of space identifiers that have zero usage."""
        return [item.space for item in self.items if item.is_empty]
