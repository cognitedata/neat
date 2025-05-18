from rdflib import RDF, XSD, Literal, Namespace

from cognite.neat.core._instances.transformers import ObjectMapper
from cognite.neat.core._store import NeatInstanceStore


class TestObjectMapper:
    def test_map_object(self) -> None:
        store = NeatInstanceStore.from_oxi_local_store()

        namespace = Namespace("http://example.com/")
        id_ = namespace["MyEvent"]
        store._add_triples(
            [
                (id_, RDF.type, namespace["Event"]),
                (id_, namespace["type"], Literal("モ語5速ち")),
            ],
            named_graph=store.default_named_graph,
        )
        mapping = {"モ語5速ち": "aliquam sed"}
        transformer = ObjectMapper(mapping, namespace["type"])

        store.transform(transformer)
        assert set(store.queries.select.list_triples(limit=3)) == {
            (id_, RDF.type, namespace["Event"]),
            (id_, namespace["type"], Literal("aliquam sed", datatype=XSD.string)),
        }
