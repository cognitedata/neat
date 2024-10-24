from cognite.neat._graph.extractors import DexpiExtractor
from cognite.neat._store import NeatGraphStore
from tests import config


def test_dexpi_extractor():
    """Test that the dexpi extractor works."""

    store = NeatGraphStore.from_memory_store()
    store.write(DexpiExtractor.from_file(config.DEXPI_EXAMPLE))

    assert len(store.graph) == 1922
