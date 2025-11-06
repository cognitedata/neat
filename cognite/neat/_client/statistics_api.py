from pydantic import BaseModel, Field

from cognite.neat._client.api import NeatAPI
from cognite.neat._data_model.models.dms._data_types import DataType, DirectNodeRelation, Int32Property, Int64Property
from cognite.neat._utils.http_client import ParametersRequest


class ResourceLimit(BaseModel):
    """Model for resources with count and limit."""

    count: int
    limit: int


class InstancesDetail(BaseModel):
    """Model for instances with detailed metrics."""

    edges: int
    soft_deleted_edges: int = Field(alias="softDeletedEdges")
    nodes: int
    soft_deleted_nodes: int = Field(alias="softDeletedNodes")
    instances: int
    instances_limit: int = Field(alias="instancesLimit")
    soft_deleted_instances: int = Field(alias="softDeletedInstances")
    soft_deleted_instances_limit: int = Field(alias="softDeletedInstancesLimit")

    class Config:
        populate_by_name = True


class StatisticsResponse(BaseModel):
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

    class Config:
        populate_by_name = True


class StatisticsAPI(NeatAPI):
    def project(self) -> StatisticsResponse:
        """Retrieve project-wide usage data and limits.

        Returns:
            StatisticsResponse object.
        """

        result = self._http_client.request_with_retries(
            ParametersRequest(
                endpoint_url=self._config.create_api_url("/models/statistics"),
                method="GET",
                parameters=None,
            )
        )

        result.raise_for_status()
        result = StatisticsResponse.model_validate_json(result.success_response.body)
        return result


class SpaceStatistics(BaseModel):
    """Statistics for spaces."""

    limit: int = 100
    count: int | None = None


class ListablePropertyStatistics(BaseModel):
    """Statistics for list properties."""

    limit: int = Field(2_000, description="Max limit for types other than int32/64 with b-tree index.")
    int32_with_btree_limit: int = Field(600, description="Max limit for Int32 properties with B-tree index.")
    int64_with_btree_limit: int = Field(300, description="Max limit for Int64 properties with B-tree index.")
    # defaults
    direct_default: int = Field(100, description="Default limit for direct relations.")
    other_default: int = Field(1_000, description="Default limit for types other than direct.")

    def __call__(self, data_type: DataType, has_btree_index: bool = False) -> int:
        """Get the limit for a specific data type."""
        if isinstance(data_type, Int32Property) and has_btree_index:
            return self.int32_with_btree_limit
        if isinstance(data_type, Int64Property) and has_btree_index:
            return self.int64_with_btree_limit
        return self.limit

    def default(self, data_type: DataType) -> int:
        """Get the default limit for a specific data type."""
        if isinstance(data_type, DirectNodeRelation):
            return self.direct_default
        return self.other_default


class ContainerPropertyStatistics(BaseModel):
    limit: int = Field(100, description="Limit of properties per container.")
    enums: int = Field(32, description="Limit of enums per property.")

    total: int = Field(25_000, description="Total limit of properties.")
    count: int | None = None

    listable: ListablePropertyStatistics = Field(default_factory=ListablePropertyStatistics)

    def __call__(self) -> int:
        return self.limit


class ContainerStatistics(BaseModel):
    """Statistics for containers."""

    limit: int = 1_000
    count: int | None = None
    properties: ContainerPropertyStatistics = Field(default_factory=ContainerPropertyStatistics)


class ViewStatistics(BaseModel):
    """Statistics for views."""

    limit: int = 2_000
    count: int | None = None
    versions: int = 100
    properties: int = 300
    implements: int = 10
    containers: int = 10


class DataModelStatistics(BaseModel):
    """Statistics for data models."""

    limit: int = 500
    count: int | None = None
    versions: int = Field(100, description="Limit of versions per data model.")
    views: int = Field(100, description="Limit of views per data model.")


class InstanceStatistics(BaseModel, populate_by_name=True):
    """Statistics for instances."""

    limit: int = Field(5_000_000, alias="instances_limit")
    count: int | None = Field(None, alias="instances")
    soft_deleted_limit: int = Field(10_000_000, alias="soft_deleted_instances_limit")
    soft_delete_count: int | None = Field(None, alias="soft_deleted_instances")


class DmsStatistics(BaseModel):
    """CDF Data Modeling resource statistics."""

    spaces: SpaceStatistics = Field(default_factory=SpaceStatistics)
    containers: ContainerStatistics = Field(default_factory=ContainerStatistics)
    views: ViewStatistics = Field(default_factory=ViewStatistics)
    data_models: DataModelStatistics = Field(default_factory=DataModelStatistics)
    instances: InstanceStatistics = Field(default_factory=InstanceStatistics)

    @classmethod
    def from_api_response(cls, response: StatisticsResponse) -> "DmsStatistics":
        """Populate limits from API response."""
        # Implementation to parse and set limits from response can be added here

        container = ContainerStatistics(**response.containers.model_dump())
        container.properties.limit = response.container_properties.limit
        container.properties.count = response.container_properties.count

        return cls(
            spaces=SpaceStatistics(**response.spaces.model_dump()),
            containers=container,
            views=ViewStatistics(**response.views.model_dump()),
            data_models=DataModelStatistics(**response.data_models.model_dump()),
            instances=InstanceStatistics(**response.instances.model_dump()),
        )
