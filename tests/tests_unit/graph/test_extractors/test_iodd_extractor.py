from cognite.neat.graph.extractors import IODDExtractor
from cognite.neat.store import NeatGraphStore
from tests.config  import IODD_EXAMPLE
from rdflib import Namespace

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


def test_num_triples():
    """Test that the dexpi extractor works."""

    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(IODD_EXAMPLE))

    # Asset total length
    assert len(store.graph) == 392

    # Asset num instances of each type
    assert len(list(store.graph.query(f"SELECT ?s WHERE {{ ?s a <{IODD.TextObject}>}}"))) == 166
    assert len(list(store.graph.query(f"SELECT ?s WHERE {{ ?s a <{IODD.IoddDevice}>}}"))) == 1
    assert len(list(store.graph.query(f"SELECT ?s WHERE {{ ?s a <{IODD.ProcessDataIn}>}}"))) == 1
