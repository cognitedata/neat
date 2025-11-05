from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.models.dms._data_types import DataType, DirectNodeRelation, Int32Property, Int64Property


class _BaseLimits(BaseModel):
    """Base class for limits."""

    model_config = ConfigDict(frozen=True)


class SpaceLimits(_BaseLimits):
    """Limits for spaces."""

    total: int = 100


class ListPropertyLimits(_BaseLimits):
    """Limits for list properties."""

    default_direct_relations: int = 100
    default_other_types: int = 1_000
    max_int32_with_btree: int = 600
    max_int64_with_btree: int = 300
    max_all_other_types: int = 2_000

    model_config = {"frozen": True}


class ContainerLimits(_BaseLimits):
    """Limits for containers."""

    total: int = 1_000
    properties_total: int = 25_000
    properties_per_container: int = 100
    enums_per_property: int = 32
    listable_property: ListPropertyLimits = Field(default_factory=ListPropertyLimits)

    model_config = {"frozen": True}

    def get_limit_for_data_type(self, data_type: DataType, has_btree_index: bool = False) -> int:
        """Get the limit for a specific data type."""
        if isinstance(data_type, DirectNodeRelation):
            return self.listable_property.default_direct_relations
        if isinstance(data_type, Int32Property) and has_btree_index:
            return self.listable_property.max_int32_with_btree
        if isinstance(data_type, Int64Property) and has_btree_index:
            return self.listable_property.max_int64_with_btree
        return self.listable_property.max_all_other_types


class ViewLimits(_BaseLimits):
    """Limits for views."""

    total: int = 2_000
    versions_per_view: int = 100
    properties_per_view: int = 300
    implements_per_view: int = 10
    containers_per_view: int = 10

    model_config = {"frozen": True}


class DataModelLimits(_BaseLimits):
    """Limits for data models."""

    versions_total: int = 500
    versions_per_data_model: int = 100
    views_per_data_model: int = 100

    model_config = {"frozen": True}


class InstanceLimits(_BaseLimits):
    """Limits for instances."""

    live: int = 5_000_000
    soft_deleted: int = 10_000_000

    model_config = {"frozen": True}


class _DMSLimits(BaseModel):
    """CDF Data Modeling resource limits."""

    space: SpaceLimits = Field(default_factory=SpaceLimits)
    container: ContainerLimits = Field(default_factory=ContainerLimits)
    view: ViewLimits = Field(default_factory=ViewLimits)
    data_model: DataModelLimits = Field(default_factory=DataModelLimits)
    instance: InstanceLimits = Field(default_factory=InstanceLimits)

    def from_api_response(self, client: NeatClient) -> None:
        """Populate limits from API response."""
        # Implementation to parse and set limits from response can be added here
        ...


DMSDefaultLimits = _DMSLimits()
