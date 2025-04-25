from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat._client.data_classes.location_filters import LocationFilterWrite
from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._graph.loaders import LocationFilterLoader
from cognite.neat._utils.upload import UploadResult


class TestLocationFilterLoader:
    def test_load_location_filter(self) -> None:
        id_ = DataModelId("my_space", "my_id", "v1")
        loader = LocationFilterLoader(
            data_model_id=id_,
            instance_spaces=["instance_space_1", "instance_space_2"],
            name="my_location_filter",
        )
        data_model_str = f"{id_.space}:{loader.data_model_id.external_id}(version={loader.data_model_id.version})"
        expected_filter = LocationFilterWrite(
            external_id="my_location_filter",
            name="my_location_filter",
            description=f"Location filter for {data_model_str}",
            data_models=[id_],
            instance_spaces=["instance_space_1", "instance_space_2"],
            data_modeling_type="DATA_MODELING_ONLY",
        )
        loaded = list(loader.load())
        assert len(loaded) == 1
        assert loaded[0] == expected_filter

        with monkeypatch_neat_client() as client:
            results = loader.load_into_cdf(client, check_client=False)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, UploadResult)
        assert len(result.created) == 1
