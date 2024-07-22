import pytest
from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformers import AddSelfReferenceProperty


@pytest.fixture()
def asset_store(asset_rules) -> NeatGraphStore:
    asset_store = NeatGraphStore.from_memory_store()
    asset_store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_store.add_rules(asset_rules.as_information_rules())
    asset_store.transform(AddSelfReferenceProperty(rules=asset_store.rules))

    return asset_store
