from cognite.neat.legacy.graph import extractors as graph_loader
from tests import config


def test_dexpi_extractor():
    """Test that the dexpi extractor works."""
    triples = graph_loader.DexpiXML(config.DEXPI_EXAMPLE).extract()

    assert len(triples) == 1752
