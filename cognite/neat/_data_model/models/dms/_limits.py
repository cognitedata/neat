from pydantic import BaseModel, Field

from cognite.neat._client.statistics_api import StatisticsResponse

from ._data_types import DataType, DirectNodeRelation, Int32Property, Int64Property


class SpaceLimit(BaseModel):
    """Limits for spaces."""

    limit: int = 100


class ListablePropertyLimits(BaseModel):
    """Limits for list properties."""

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


class ContainerPropertyLimits(BaseModel):
    limit: int = Field(100, description="Limit of properties per container.")
    enums: int = Field(32, description="Limit of enums per property.")
    total: int = Field(25_000, description="Total limit of properties.")

    listable: ListablePropertyLimits = Field(default_factory=ListablePropertyLimits)

    def __call__(self) -> int:
        return self.limit


class ContainerLimits(BaseModel):
    """Limits for containers."""

    limit: int = 1_000
    properties: ContainerPropertyLimits = Field(default_factory=ContainerPropertyLimits)


class ViewLimits(BaseModel):
    """Limits for views."""

    limit: int = 2_000
    versions: int = 100
    properties: int = 300
    implements: int = 10
    containers: int = 10


class DataModelLimits(BaseModel):
    """Limits for data models."""

    limit: int = 500
    versions: int = Field(100, description="Limit of versions per data model.")
    views: int = Field(100, description="Limit of views per data model.")


class SchemaLimits(BaseModel):
    """CDF Data Modeling resource limits."""

    spaces: SpaceLimit = Field(default_factory=SpaceLimit)
    containers: ContainerLimits = Field(default_factory=ContainerLimits)
    views: ViewLimits = Field(default_factory=ViewLimits)
    data_models: DataModelLimits = Field(default_factory=DataModelLimits)

    @classmethod
    def from_api_response(cls, response: StatisticsResponse) -> "SchemaLimits":
        """Populate limits from API response."""
        # Implementation to parse and set limits from response can be added here

        container = ContainerLimits(**response.containers.model_dump())
        container.properties.limit = response.container_properties.limit

        return cls(
            spaces=SpaceLimit(**response.spaces.model_dump()),
            containers=container,
            views=ViewLimits(**response.views.model_dump()),
            data_models=DataModelLimits(**response.data_models.model_dump()),
        )
