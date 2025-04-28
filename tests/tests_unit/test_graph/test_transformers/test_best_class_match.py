import urllib.parse

from rdflib import RDF, Literal, Namespace

from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._graph.transformers import BestClassMatch
from cognite.neat.core._issues.warnings import MultiClassFoundWarning, PartialClassFoundWarning
from cognite.neat.core._store import NeatGraphStore


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

    def test_multi_classes_match(self) -> None:
        store = NeatGraphStore.from_oxi_local_store()
        namespace = Namespace(DEFAULT_SPACE_URI.format(space="sp_instance_space"))
        schema_ns = Namespace("http://example.com/schema/")
        id_ = namespace[urllib.parse.quote("MyInstanceッ差")]

        # Write a car instance to the store.
        store._add_triples(
            [
                (id_, RDF.type, namespace["Unknown"]),
                (id_, schema_ns["wheels"], Literal(4)),
                (id_, schema_ns["engine"], Literal("V8")),
            ],
            named_graph=store.default_named_graph,
        )

        transformer = BestClassMatch(
            classes={
                schema_ns["SportsCarッ"]: frozenset({"wheels", "engine"}),
                schema_ns["Truckッ"]: frozenset({"wheels", "engine"}),
            }
        )

        issues = store.transform(transformer)

        assert len(issues) == 1

        assert issues[0] == MultiClassFoundWarning(
            instance="sp_instance_space:MyInstanceッ差",
            selected_class="SportsCarッ",
            alternatives=frozenset({"Truckッ"}),
        )
