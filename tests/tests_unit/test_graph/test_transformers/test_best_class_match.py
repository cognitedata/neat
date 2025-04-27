from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.transformers import BestClassMatch
from cognite.neat._issues.warnings import PartialClassFoundWarning
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
            ],
            named_graph=store.default_named_graph,
        )
        transformer = BestClassMatch(
            classes={
                namespace["Car"]: frozenset({"wheels", "engine"}),
                namespace["Bike"]: frozenset({"wheels"}),
            }
        )
        issues = store.transform(transformer)
        assert len(issues) == 1
        assert issues[0] == PartialClassFoundWarning("MyInstance", "Car", 1, frozenset({"color"}))

        results = store.queries.select.types_with_instance_and_property_count(remove_namespace=True)

        assert len(results) == 1
        result = results[0]
        assert result == {
            "type": "Car",
            "instanceCount": 1,
            "propertyCount": 3,
        }
