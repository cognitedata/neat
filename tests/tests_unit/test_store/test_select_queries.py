from rdflib import RDF, Literal

from cognite.neat.core._constants import DEFAULT_NAMESPACE
from cognite.neat.core._store import NeatInstanceStore


class TestListInstanceObjectIds:
    def test_list_instance_object_ids(self) -> None:
        store = NeatInstanceStore.from_oxi_local_store()
        my_entity = DEFAULT_NAMESPACE["my_entity"]
        my_other_entity = DEFAULT_NAMESPACE["my_other_entity"]
        store._add_triples(
            [
                (my_entity, RDF.type, DEFAULT_NAMESPACE["Entity"]),
                (my_entity, DEFAULT_NAMESPACE["name"], Literal("My Entity")),
                (my_entity, DEFAULT_NAMESPACE["connection"], my_other_entity),
                (my_other_entity, RDF.type, DEFAULT_NAMESPACE["Entity"]),
            ],
            named_graph=store.default_named_graph,
        )

        result = list(store.queries.select.list_instance_object_ids())

        assert len(result) == 1
        assert result[0] == my_other_entity
