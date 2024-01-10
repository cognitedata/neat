from cognite.neat.graph import extractors
from tests import config


def test_dexpi_extractor():
    """Test that the dexpi extractor works."""
    extractor = extractors.DexpiXML(config.DEXPI_EXAMPLE)
    triples = extractor.extract()

    assert len(triples) == 1752
