import urllib.parse

from rdflib import RDF, Namespace

from cognite.neat.v0.core._instances.transformers import ConnectionToLiteral
from cognite.neat.v0.core._store import NeatInstanceStore


class TestConnectionToLiteral:
    def test_connection_to_literal_non_alpha_numeric(self) -> None:
        store = NeatInstanceStore.from_memory_store()
        namespace = Namespace("http://example.com/")
        asset_id = namespace["MyAsset"]
        label_id = namespace[urllib.parse.quote("写ラミリヒ押報メ")]
        # Write a car instance to the store.
        store._add_triples(
            [
                (asset_id, RDF.type, namespace["Asset"]),
                (asset_id, namespace["labels"], label_id),
                (label_id, RDF.type, namespace["Label"]),
            ],
            named_graph=store.default_named_graph,
        )
        transformer = ConnectionToLiteral(
            subject_type=namespace["Asset"],
            subject_predicate=namespace["labels"],
        )
        issues = store.transform(transformer)
        assert len(issues) == 0

        actual_id, properties = store.queries.select.describe(asset_id)

        assert actual_id == asset_id
        assert dict(properties) == {
            RDF.type: ["Asset"],
            "labels": ["写ラミリヒ押報メ"],
        }
