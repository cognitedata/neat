from rdflib import Namespace

from cognite.neat._graph.extractors import IODDExtractor
from cognite.neat._graph.transformers._iodd import IODDPruneDanglingNodes, IODDTwoHopFlattener
from cognite.neat._store import NeatGraphStore
from tests.config import IODD_EXAMPLE

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


def test_two_hop_flattener():
    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(IODD_EXAMPLE))

    flatten_iodd = IODDTwoHopFlattener()
    flatten_iodd.transform(store.graph)

    triples = [triple for triple in store.graph.triples((None, None, None))]

    assert len(triples) == 386


def test_prune_dangling_nodes():
    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(IODD_EXAMPLE))

    flatten_iodd = IODDTwoHopFlattener()
    flatten_iodd.transform(store.graph)

    prune_transformer = IODDPruneDanglingNodes()

    prune_transformer.transform(store.graph)

    triples = [triple for triple in store.graph.triples((None, None, None))]

    assert len(triples) == 60
