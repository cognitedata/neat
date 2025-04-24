from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.core._client import NeatClient
from cognite.neat.core._client.data_classes.location_filters import LocationFilterWrite


class TestLocationFilter:
    def test_create_list_retrieve_delete(self, neat_client: NeatClient) -> None:
        my_filter = LocationFilterWrite(
            external_id="neat_testing_filter",
            name="neat_testing_filter",
            description="This is part of the integration tests for Neat",
            data_models=[DataModelId("cdf_cdm", "CogniteCore", "v1")],
            instance_spaces=["my_space", "my_other_space"],
            data_modeling_type="DATA_MODELING_ONLY",
        )
        created_id: int | None = None

        try:
            created = neat_client.location_filters.create(my_filter)
            created_id = created.id

            assert created.external_id == my_filter.external_id

            listed = neat_client.location_filters.list()

            assert any(listed.external_id == my_filter.external_id for listed in listed), (
                "The location filter should be listed"
            )

            retrieved = neat_client.location_filters.retrieve(created.id)

            assert retrieved.external_id == my_filter.external_id

        finally:
            if created_id is not None:
                neat_client.location_filters.delete(created_id)
