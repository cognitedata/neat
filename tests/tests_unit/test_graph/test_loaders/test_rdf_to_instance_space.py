import pytest
from cognite.client.data_classes import AssetWriteList

from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._graph.extractors import AssetsExtractor
from cognite.neat._graph.loaders import InstanceSpaceLoader
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.upload import UploadResult
from tests.data import InstanceData


def load_instance_spaces_test_cases():
    """Test cases for instance space exporter."""
    yield pytest.param(InstanceSpaceLoader(instance_space="my_space"), {"my_space"}, id="Simple single space")

    store = NeatGraphStore.from_memory_store()

    store.write(
        extractor=AssetsExtractor(
            AssetWriteList.load(InstanceData.AssetCentricCDF.assets_yaml.read_text()), identifier="id"
        )
    )

    yield pytest.param(
        InstanceSpaceLoader(graph_store=store, space_property="dataSetId"),
        {"6931754270713290"},
        id="Space from property",
    )


class TestInstanceSpaceLoader:
    @pytest.mark.parametrize("exporter, expected_spaces", list(load_instance_spaces_test_cases()))
    def test_export_instance_space(self, exporter: InstanceSpaceLoader, expected_spaces: set[str]) -> None:
        loaded = list(exporter.load())

        assert {space.space for space in loaded} == expected_spaces

        with monkeypatch_neat_client() as client:
            results = exporter.load_into_cdf(client, check_client=False)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, UploadResult)
        assert result.created == expected_spaces
