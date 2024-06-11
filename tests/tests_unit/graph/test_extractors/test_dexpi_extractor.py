from cognite.neat.graph.extractors import DexpiExtractor
from cognite.neat.graph.stores import NeatGraphStore
from tests import config


def test_dexpi_extractor():
    """Test that the dexpi extractor works."""

    store = NeatGraphStore.from_memory_store()
    store.write(DexpiExtractor(config.DEXPI_EXAMPLE))

    assert len(store.graph) == 1716
