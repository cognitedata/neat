from rdflib import RDF, XSD, Literal, Namespace

from cognite.neat.core._instances.transformers import ObjectMapper
from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._store import NeatInstanceStore


class TestObjectMapper:
    def test_map_object(self) -> None:
        store = NeatInstanceStore.from_oxi_local_store()

        namespace = Namespace("http://example.com/")
        id_ = namespace["MyEvent"]
        other_event = namespace["OtherEvent"]
        store._add_triples(
            [
                (id_, RDF.type, namespace["Event"]),
                (id_, namespace["type"], Literal("モ語5速ち")),
                (other_event, RDF.type, namespace["Event"]),
                (id_, namespace["type"], Literal("missing-in-mapping")),
            ],
            named_graph=store.default_named_graph,
        )
        mapping = {"モ語5速ち": "aliquam sed"}
        transformer = ObjectMapper(mapping, namespace["type"])

        issues = store.transform(transformer)
        assert set(store.queries.select.list_triples(limit=5)) == {
            (id_, RDF.type, namespace["Event"]),
            (id_, namespace["type"], Literal("aliquam sed", datatype=XSD.string)),
            (other_event, RDF.type, namespace["Event"]),
            (id_, namespace["type"], Literal("missing-in-mapping", datatype=XSD.string)),
        }
        assert len(issues) == 1
        assert issues[0] == NeatValueWarning(
            "MyEvent could not map type: 'missing-in-mapping'. It does not exist in the given mapping."
        )
