from rdflib import Namespace

from cognite.neat._graph.extractors import IODDExtractor
from cognite.neat._store import NeatGraphStore
from tests.data import GraphData

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


def test_num_triples():
    """Test that the dexpi extractor works."""

    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(GraphData.iodd_Piab_piCOMPACT10X_20230509_IODD1_1_xml))

    # Asset total length
    assert len(store.dataset) == 392

    # Asset num instances of each type
    assert len(list(store.dataset.query(f"SELECT ?s WHERE {{ ?s a <{IODD.TextObject}>}}"))) == 166
    assert len(list(store.dataset.query(f"SELECT ?s WHERE {{ ?s a <{IODD.IoddDevice}>}}"))) == 1
    assert len(list(store.dataset.query(f"SELECT ?s WHERE {{ ?s a <{IODD.ProcessDataIn}>}}"))) == 1
