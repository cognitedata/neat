from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.models.dms._data_types import DataType, DirectNodeRelation, Int32Property, Int64Property


class _BaseStatistics(BaseModel):
    """Base class for DMS statistics."""

    model_config = ConfigDict(frozen=True)


class SpaceStatistics(_BaseStatistics):
    """Statistics for spaces."""

    limit: int = 100
    count: int | None = None


class ListablePropertyStatistics(_BaseStatistics):
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


class ContainerPropertyStatistics(_BaseStatistics):
    limit: int = 100
    enums: int = Field(32, description="Limit of enums per property.")

    total: int = Field(25_000, description="Total limit of properties.")
    count: int | None = None

    listable: ListablePropertyStatistics = Field(default_factory=ListablePropertyStatistics)

    def __call__(self) -> int:
        return self.limit


class ContainerStatistics(_BaseStatistics):
    """Statistics for containers."""

    limit: int = 1_000
    count: int | None = None
    properties: ContainerPropertyStatistics = Field(default_factory=ContainerPropertyStatistics)


class ViewStatistics(_BaseStatistics):
    """Statistics for views."""

    limit: int = 2_000
    count: int | None = None
    versions: int = 100
    properties: int = 300
    implements: int = 10
    containers: int = 10


class DataModelStatistics(_BaseStatistics):
    """Statistics for data models."""

    limit: int = 500
    count: int | None = None
    versions: int = Field(100, description="Limit of versions per data model.")
    views: int = Field(100, description="Limit of views per data model.")


class InstanceStatistics(_BaseStatistics):
    """Statistics for instances."""

    limit: int = 5_000_000
    count: int | None = None
    soft_deleted_limit: int = 10_000_000
    soft_delete_count: int | None = None


class _DMSStatistics(BaseModel):
    """CDF Data Modeling resource statistics."""

    space: SpaceStatistics = Field(default_factory=SpaceStatistics)
    container: ContainerStatistics = Field(default_factory=ContainerStatistics)
    view: ViewStatistics = Field(default_factory=ViewStatistics)
    data_model: DataModelStatistics = Field(default_factory=DataModelStatistics)
    instance: InstanceStatistics = Field(default_factory=InstanceStatistics)

    def from_api_response(self, client: NeatClient) -> None:
        """Populate limits from API response."""
        # Implementation to parse and set limits from response can be added here
        ...


DMSDefaultLimits = _DMSStatistics()
