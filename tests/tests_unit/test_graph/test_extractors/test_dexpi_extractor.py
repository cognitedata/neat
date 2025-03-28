from cognite.neat._graph.extractors import DexpiExtractor
from cognite.neat._store import NeatGraphStore
from tests.data import GraphData


def test_dexpi_extractor():
    """Test that the dexpi extractor works."""

    store = NeatGraphStore.from_memory_store()
    store.write(DexpiExtractor.from_file(GraphData.dexpi_example_xml))

    assert len(store.dataset) == 1922
