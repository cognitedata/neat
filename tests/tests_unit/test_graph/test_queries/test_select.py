from rdflib import RDF, Literal, Namespace

from cognite.neat._store import NeatGraphStore


class TestPropertiesWithCount:
    def test_properties_with_count(self) -> None:
        store = NeatGraphStore.from_oxi_local_store()

        ns = Namespace("http://example.org/")
        car = ns["MyCar"]
        bike1 = ns["Bike1"]
        bike2 = ns["Bike2"]
        store._add_triples(
            [
                (car, RDF.type, ns["Car"]),
                (car, ns["engine"], Literal("V8")),
                (car, ns["wheels"], Literal(4)),
                (bike1, RDF.type, ns["Bike"]),
                (bike1, ns["wheels"], Literal(2)),
                (bike2, RDF.type, ns["Bike"]),
                (bike2, ns["wheels"], Literal(3)),
            ],
            named_graph=store.default_named_graph,
        )

        result = store.queries.select.properties_with_count(remove_namespace=True)

        assert result == [
            {
                "type": "Car",
                "property": "engine",
                "cardinality": 1,
                "instanceCount": 1,
                "total": 1,
            },
            {
                "type": "Car",
                "property": "wheels",
                "cardinality": 1,
                "instanceCount": 1,
                "total": 1,
            },
            {
                "type": "Bike",
                "property": "wheels",
                "cardinality": 2,
                "instanceCount": 2,
                "total": 2,
            },
        ]
