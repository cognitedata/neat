from rdflib import Dataset, Graph, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID


class BaseQuery:
    def __init__(
        self,
        dataset: Dataset,
        default_named_graph: URIRef | None = None,
    ):
        self.dataset = dataset
        self.default_named_graph = default_named_graph or DATASET_DEFAULT_GRAPH_ID

    def graph(self, named_graph: URIRef | None = None) -> Graph:
        """Get named graph from the dataset to query over"""
        return self.dataset.graph(named_graph or self.default_named_graph)
