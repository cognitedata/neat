from cognite.neat.graph.extractors import IODDExtractor
from cognite.neat.store import NeatGraphStore
from cognite.neat.graph.transformers._iodd import IODDTwoHopFlattener, IODDPruneDanglingNodes

from tests.config  import IODD_EXAMPLE
from rdflib import Namespace

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
