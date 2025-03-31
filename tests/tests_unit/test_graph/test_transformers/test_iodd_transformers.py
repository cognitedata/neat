from rdflib import Namespace

from cognite.neat._graph.extractors import IODDExtractor
from cognite.neat._graph.transformers._iodd import IODDAttachPropertyFromTargetToSource, IODDPruneDanglingNodes
from cognite.neat._store import NeatGraphStore
from tests.data import GraphData

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


def test_iodd_attach_property_from_target_to_source():
    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(GraphData.iodd_Piab_piCOMPACT10X_20230509_IODD1_1_xml))

    flatten_iodd = IODDAttachPropertyFromTargetToSource()
    flatten_iodd.transform(store.dataset)

    triples = [triple for triple in store.dataset.triples((None, None, None))]

    assert len(triples) == 386


def test_prune_dangling_nodes():
    store = NeatGraphStore.from_memory_store()
    store.write(IODDExtractor.from_file(GraphData.iodd_Piab_piCOMPACT10X_20230509_IODD1_1_xml))

    flatten_iodd = IODDAttachPropertyFromTargetToSource()
    flatten_iodd.transform(store.dataset)

    prune_transformer = IODDPruneDanglingNodes()

    prune_transformer.transform(store.dataset)

    triples = [triple for triple in store.dataset.triples((None, None, None))]

    assert len(triples) == 60
