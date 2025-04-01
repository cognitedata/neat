from rdflib import Dataset, URIRef

from ._select import SelectQueries
from ._update import UpdateQueries


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(
        self,
        dataset: Dataset,
        default_named_graph: URIRef | None = None,
    ) -> None:
        self.select = SelectQueries(dataset, default_named_graph)
        self.update = UpdateQueries(self.select, dataset, default_named_graph)
