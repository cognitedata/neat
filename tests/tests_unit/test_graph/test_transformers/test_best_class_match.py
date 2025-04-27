from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.transformers import BestClassMatch
from cognite.neat._store import NeatGraphStore


class TestBestClassMatch:
    def test_find_best_class_match(self) -> None:
        store = NeatGraphStore.from_memory_store()
        namespace = Namespace("http://example.com/")
        id_ = namespace["MyInstance"]
        # Write a car instance to the store.
        store._add_triples(
            [
                (id_, RDF.type, namespace["Unknown"]),
                (id_, namespace["wheels"], Literal(4)),
                (id_, namespace["color"], Literal("red")),
                (id_, namespace["engine"], Literal("V8")),
            ]
        )
        transformer = BestClassMatch(
            classes={
                namespace["Car"]: frozenset({namespace["wheels"], namespace["engine"]}),
                namespace["Bike"]: frozenset({namespace["wheels"]}),
            }
        )
        store.transform(transformer)

        results = store.queries.select.types_with_instance_and_property_count(remove_namespace=True)

        assert len(results) == 1
        result = results[0]
        assert result == {
            "type": "Car",
            "instance_count": 1,
            "property_count": 3,
        }
