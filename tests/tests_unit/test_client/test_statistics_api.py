import pytest
import respx

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes import (
    InstancesDetail,
    ResourceLimit,
    StatisticsResponse,
)
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._exceptions import CDFAPIException


class TestStatisticsAPI:
    def test_project_statistics(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_statistics_response: dict
    ) -> None:
        """Test retrieving project-wide statistics."""
        client = neat_client
        config = client.config

        respx_mock.get(
            config.create_api_url("/models/statistics"),
        ).respond(
            status_code=200,
            json=example_statistics_response,
        )

        stats = client.statistics.project()

        assert isinstance(stats, StatisticsResponse)
        assert stats.spaces.count == 5
        assert stats.spaces.limit == 100
        assert stats.containers.count == 42
        assert stats.containers.limit == 1000
        assert stats.views.count == 123
        assert stats.views.limit == 2000
        assert stats.data_models.count == 8
        assert stats.data_models.limit == 500
        assert stats.container_properties.count == 1234
        assert stats.container_properties.limit == 100
        assert stats.instances.nodes == 10000
        assert stats.instances.edges == 5000
        assert stats.instances.instances == 15000
        assert stats.instances.instances_limit == 5000000
        assert stats.concurrent_read_limit == 10
        assert stats.concurrent_write_limit == 5
        assert stats.concurrent_delete_limit == 3

        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert call.request.method == "GET"
        assert "/models/statistics" in str(call.request.url)

    def test_instances_detail_model(self, example_statistics_response: dict) -> None:
        """Test InstancesDetail model parsing with snake_case and camelCase."""
        instances_data = example_statistics_response["instances"]
        instances = InstancesDetail.model_validate(instances_data)

        assert instances.edges == 5000
        assert instances.soft_deleted_edges == 100
        assert instances.nodes == 10000
        assert instances.soft_deleted_nodes == 200
        assert instances.instances == 15000
        assert instances.instances_limit == 5000000
        assert instances.soft_deleted_instances == 300
        assert instances.soft_deleted_instances_limit == 10000000

    def test_resource_limit_model(self) -> None:
        """Test ResourceLimit model parsing."""
        data = {"count": 42, "limit": 100}
        resource = ResourceLimit.model_validate(data)

        assert resource.count == 42
        assert resource.limit == 100

    def test_statistics_response_model(self, example_statistics_response: dict) -> None:
        """Test full StatisticsResponse model validation."""
        response = StatisticsResponse.model_validate(example_statistics_response)

        assert isinstance(response.spaces, ResourceLimit)
        assert isinstance(response.containers, ResourceLimit)
        assert isinstance(response.views, ResourceLimit)
        assert isinstance(response.data_models, ResourceLimit)
        assert isinstance(response.container_properties, ResourceLimit)
        assert isinstance(response.instances, InstancesDetail)
        assert response.concurrent_read_limit == 10
        assert response.concurrent_write_limit == 5
        assert response.concurrent_delete_limit == 3

    def test_dms_statistics_from_api_response(self, example_statistics_response: dict) -> None:
        """Test DmsStatistics creation from API response."""
        api_response = StatisticsResponse.model_validate(example_statistics_response)
        dms_stats = SchemaLimits.from_api_response(api_response)

        assert isinstance(dms_stats, SchemaLimits)
        assert dms_stats.spaces.limit == 100
        assert dms_stats.containers.limit == 1000
        assert dms_stats.containers.properties.limit == 100
        assert dms_stats.views.limit == 2000
        assert dms_stats.data_models.limit == 500

    def test_listable_property_limits(self) -> None:
        """Test ListablePropertyStatistics limit calculation."""
        dms_stats = SchemaLimits()
        listable = dms_stats.containers.properties.listable

        # Test default limits
        from cognite.neat._data_model.models.dms._data_types import (
            DirectNodeRelation,
            Int32Property,
            Int64Property,
            TextProperty,
        )

        # Int32 with btree
        int32_type = Int32Property()
        assert listable(int32_type, has_btree_index=True) == 600
        assert listable(int32_type, has_btree_index=False) == 2000

        # Int64 with btree
        int64_type = Int64Property()
        assert listable(int64_type, has_btree_index=True) == 300
        assert listable(int64_type, has_btree_index=False) == 2000

        # Text (no btree affects limit)
        text_type = TextProperty()
        assert listable(text_type, has_btree_index=True) == 2000
        assert listable(text_type, has_btree_index=False) == 2000

        # Default limits
        direct_relation = DirectNodeRelation()
        assert listable.default(direct_relation) == 100
        assert listable.default(text_type) == 1000

    def test_statistics_api_error_handling(self, neat_client: NeatClient, respx_mock: respx.MockRouter) -> None:
        """Test error handling when API returns error."""
        client = neat_client
        config = client.config

        respx_mock.get(
            config.create_api_url("/models/statistics"),
        ).respond(
            status_code=500,
            json={"error": {"message": "Internal server error"}},
        )

        with pytest.raises(CDFAPIException):
            client.statistics.project()

        assert len(respx_mock.calls) == 1

    def test_container_property_statistics_callable(self) -> None:
        """Test ContainerPropertyStatistics as callable."""
        dms_stats = SchemaLimits()
        container_props = dms_stats.containers.properties

        assert container_props() == 100  # Default limit per container
        assert container_props.enums == 32
        assert container_props.total == 25_000
