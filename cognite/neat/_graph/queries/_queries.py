from rdflib import Dataset, URIRef

from ._read import ReadQueries
from ._write import WriteQueries


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(
        self,
        dataset: Dataset,
        default_named_graph: URIRef | None = None,
    ) -> None:
        self.read = ReadQueries(dataset, default_named_graph)
        self.write = WriteQueries(self.read, dataset, default_named_graph)
