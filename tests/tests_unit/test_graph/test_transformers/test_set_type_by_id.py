from rdflib import RDF, Namespace

from cognite.neat.core._graph.transformers import SetRDFTypeById
from cognite.neat.core._store import NeatGraphStore


class TestSetRDFTypeById:
    def test_set_rdf_type_by_id(self) -> None:
        store = NeatGraphStore.from_memory_store()
        namespace = Namespace("http://example.com/")
        id1 = namespace["Asset1"]
        id2 = namespace["Asset2"]
        id3 = namespace["Asset3"]
        store._add_triples(
            [
                (id1, RDF.type, namespace["Asset"]),
                (id2, RDF.type, namespace["Asset"]),
                (id3, RDF.type, namespace["Asset"]),
            ],
            named_graph=store.default_named_graph,
        )
        transformer = SetRDFTypeById(
            type_by_id={
                "Asset1": namespace["Car"],
                "Asset2": namespace["Bike"],
                "Asset3": namespace["Truck"],
            }
        )
        issues = store.transform(transformer)
        assert len(issues) == 0

        results = store.queries.select.list_triples()

        assert len(results) == 3
        assert set(results) == {
            (id1, RDF.type, namespace["Car"]),
            (id2, RDF.type, namespace["Bike"]),
            (id3, RDF.type, namespace["Truck"]),
        }
