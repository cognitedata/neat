from collections.abc import Iterable
from typing import Any

import pytest
from cognite.client.data_classes import AssetWriteList
from cognite.client.data_classes.data_modeling import SpaceApply
from rdflib import RDF, Literal, Namespace

from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE, DEFAULT_SPACE_URI
from cognite.neat.v0.core._instances.extractors import AssetsExtractor, BaseExtractor
from cognite.neat.v0.core._instances.loaders import InstanceSpaceLoader
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._store import NeatInstanceStore
from cognite.neat.v0.core._utils.upload import UploadResult
from tests.v0.data import InstanceData


def load_instance_spaces_test_cases() -> Iterable:
    """Test cases for instance space exporter."""
    yield pytest.param(InstanceSpaceLoader(instance_space="my_space"), {"my_space"}, id="Simple single space")

    store = NeatInstanceStore.from_memory_store()

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

    store_from_cdf = NeatInstanceStore.from_memory_store()

    class CDFMockExtractor(BaseExtractor):
        def extract(self) -> Iterable[Triple]:
            namespace = Namespace(DEFAULT_SPACE_URI.format(space="source_space"))
            yield namespace["my_instance"], RDF.type, namespace["CogniteAsset"]

    store_from_cdf.write(CDFMockExtractor())
    yield pytest.param(
        InstanceSpaceLoader(graph_store=store_from_cdf, use_source_space=True), {"source_space"}, id="Space from source"
    )

    store2 = NeatInstanceStore.from_oxi_local_store()
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


def load_instance_space_invalid_test_cases() -> Iterable:
    """Test cases for invalid instance space exporter."""
    yield pytest.param(
        {"graph_store": None, "space_property": "dataSetId", "instance_space": "fallback_space"},
        ValueError("Graph store must be provided to lookup spaces"),
        id="No graph store",
    )
    yield pytest.param(
        {"graph_store": NeatInstanceStore.from_memory_store(), "space_property": "dataSetId", "instance_space": None},
        ValueError("Missing fallback instance space. This is required when using space_property='dataSetId'"),
        id="Missing fallback space",
    )
    yield pytest.param(
        {
            "graph_store": NeatInstanceStore.from_memory_store(),
            "space_property": "dataSetId",
            "instance_space": "instance_space",
            "use_source_space": True,
        },
        ValueError("Either 'instance_space', 'space_property', or 'use_source_space' must be provided."),
        id="All three options provided",
    )


class TestInstanceSpaceLoader:
    @pytest.mark.parametrize("exporter, expected_spaces", list(load_instance_spaces_test_cases()))
    def test_export_instance_space(self, exporter: InstanceSpaceLoader, expected_spaces: set[str]) -> None:
        loaded = [result for result in exporter.load() if isinstance(result, SpaceApply)]

        assert {space.space for space in loaded} == expected_spaces

        with monkeypatch_neat_client() as client:
            results = exporter.load_into_cdf(client, check_client=False)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, UploadResult)
        assert result.created == expected_spaces

    @pytest.mark.parametrize("args, expected_exception", list(load_instance_space_invalid_test_cases()))
    def test_export_instance_space_invalid(self, args: dict[str, Any], expected_exception: Exception) -> None:
        with pytest.raises(type(expected_exception)) as excinfo:
            exporter = InstanceSpaceLoader(**args)
            list(exporter.load())

        assert str(excinfo.value) == str(expected_exception)

    def test_issue_if_missing_space(self) -> None:
        store = NeatInstanceStore.from_oxi_local_store()
        store._add_triples(
            [
                (DEFAULT_NAMESPACE["my_instance2"], RDF.type, DEFAULT_NAMESPACE["CogniteAsset"]),
            ],
            named_graph=store.default_named_graph,
        )

        loader = InstanceSpaceLoader(graph_store=store, use_source_space=True)

        issues = list(loader.load(stop_on_exception=False))

        assert len(issues) == 1
        assert issues[0].as_message() == (
            "ResourceCreationError: Failed to create instance with identifier "
            "http://purl.org/cognite/neat/my_instance2. The error was: This instance "
            "was not extracted from CDF."
        )
