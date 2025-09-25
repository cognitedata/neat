from rdflib import Dataset, URIRef

from cognite.neat.v0.core._utils.rdf_ import remove_instance_ids_in_batch

from ._base import BaseQuery
from ._select import SelectQueries


class UpdateQueries(BaseQuery):
    """This class holds a set of SPARQL queries which are updating triples in the knowledge graph.
    The update queries are executed against update endpoint, and typically start with UPDATE statement
    """

    def __init__(self, read: SelectQueries, dataset: Dataset, default_named_graph: URIRef | None = None) -> None:
        super().__init__(dataset, default_named_graph)
        self._read = read

    def drop_types(
        self,
        type_: list[URIRef],
        named_graph: URIRef | None = None,
    ) -> dict[URIRef, int]:
        """Drop types from the graph store

        Args:
            type_: List of types to drop
            named_graph: Named graph to query over, default None (default graph

        Returns:
            Dictionary of dropped types
        """
        dropped_types: dict[URIRef, int] = {}
        for t in type_:
            instance_ids = list(self._read.list_instances_ids(t))
            dropped_types[t] = len(instance_ids)
            remove_instance_ids_in_batch(self.graph(named_graph), instance_ids)
        return dropped_types
