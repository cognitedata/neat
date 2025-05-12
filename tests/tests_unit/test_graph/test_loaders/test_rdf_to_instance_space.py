from collections.abc import Iterable

import pytest
from cognite.client.data_classes import AssetWriteList
from rdflib import RDF, Literal, Namespace

from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._graph.extractors import AssetsExtractor, BaseExtractor
from cognite.neat.core._graph.loaders import InstanceSpaceLoader
from cognite.neat.core._shared import Triple
from cognite.neat.core._store import NeatGraphStore
from cognite.neat.core._utils.upload import UploadResult
from tests.data import InstanceData


def load_instance_spaces_test_cases():
    """Test cases for instance space exporter."""
    yield pytest.param(InstanceSpaceLoader(instance_space="my_space"), {"my_space"}, id="Simple single space")

    store = NeatGraphStore.from_memory_store()

    store.write(
        extractor=AssetsExtractor(
            AssetWriteList.load(InstanceData.AssetCentricCDF.assets_yaml.read_text()), identifier="externalId"
        )
    )

    yield pytest.param(
        InstanceSpaceLoader(graph_store=store, space_property="dataSetId", instance_space="fallback_space"),
        {"data_set_6931754270713290"},
        id="Space from property",
    )

    store_from_cdf = NeatGraphStore.from_memory_store()

    class CDFMockExtractor(BaseExtractor):
        def extract(self) -> Iterable[Triple]:
            namespace = Namespace(DEFAULT_SPACE_URI.format(space="source_space"))
            yield namespace["my_instance"], RDF.type, namespace["CogniteAsset"]

    store_from_cdf.write(CDFMockExtractor())
    yield pytest.param(
        InstanceSpaceLoader(graph_store=store_from_cdf, use_source_space=True), {"source_space"}, id="Space from source"
    )

    store2 = NeatGraphStore.from_oxi_local_store()
    namespace1 = Namespace(DEFAULT_SPACE_URI.format(space="space1"))
    namespace2 = Namespace(DEFAULT_SPACE_URI.format(space="space2"))
    schema_space = Namespace(DEFAULT_SPACE_URI.format(space="sp_schema"))

    class DummyExtractor(BaseExtractor):
        def extract(self) -> Iterable[Triple]:
            asset2 = namespace2["my_instance2"]
            yield asset2, RDF.type, schema_space["Asset"]
            yield asset2, schema_space["name"], Literal("My Instance")
            yield asset2, schema_space["parent"], namespace1["my_instance"]

    store2.write(DummyExtractor())

    yield pytest.param(
        InstanceSpaceLoader(graph_store=store2, use_source_space=True), {"space1", "space2"}, id="Space as object"
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
