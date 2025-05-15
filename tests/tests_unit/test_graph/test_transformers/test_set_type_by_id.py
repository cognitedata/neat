from rdflib import RDF, Namespace

from cognite.neat.core._instances.transformers import SetRDFTypeById
from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._store import NeatInstanceStore


class TestSetRDFTypeById:
    def test_set_rdf_type_by_id(self) -> None:
        store = NeatInstanceStore.from_memory_store()
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
            },
            warn_missing_instances=True,
        )
        issues = store.transform(transformer)
        assert len(issues) == 1
        warn = issues[0]
        assert isinstance(warn, NeatValueWarning)
        assert warn.value.startswith("Cannot change type of 'Asset3'")

        results = store.queries.select.list_triples()

        assert len(results) == 3
        assert set(results) == {
            (id1, RDF.type, namespace["Car"]),
            (id2, RDF.type, namespace["Bike"]),
            (id3, RDF.type, namespace["Asset"]),
        }
