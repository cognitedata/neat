import logging
import pandas as pd

from rdflib import Graph, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.utils.utils import remove_namespace

from ._base import NeatGraphStoreBase


class MemoryStore(NeatGraphStoreBase):
    """MemoryStore is a class that stores the graph in memory using rdflib and provides
    methods to read/write data it contains.


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        base_prefix : Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
        namespace : Namespace (aka URI) used to resolve any relative URI in the graph
        prefixes : Dictionary of additional prefixes used and bounded to the graph
    """

    rdf_store_type: str = "memory"

    def __init__(
        self,
        graph: Graph | None = None,
        base_prefix: str = "",  # usually empty
        namespace: Namespace = DEFAULT_NAMESPACE,
        prefixes: dict = PREFIXES,
    ):
        # Init repeated to get nice docstring
        super().__init__(graph, base_prefix, namespace, prefixes)

    def _set_graph(self):
        logging.info("Initializing graph in memory")
        self.graph = Graph()

    def drop(self):
        """Drops the graph."""
        # In the case of in-memory graph, we just reinitialize the graph
        # otherwise we would lose the prefixes and bindings, which fails
        # workflow
        self.reinit_graph()


class OpenWorld(MemoryStore):
    def describe(self, uri: str | URIRef, language: str = "en"):
        data = []
        for _, p, o in list(self.query(f"DESCRIBE <{uri}>")):
            if isinstance(o, Literal) and o.language and o.language == language:
                data.append({"Property": remove_namespace(p), "Value": o})
            elif isinstance(o, Literal) and not o.language:
                data.append({"Property": remove_namespace(p), "Value": o})
            elif isinstance(o, URIRef):
                data.append({"Property": remove_namespace(p), "Value": remove_namespace(o)})
        return pd.DataFrame(data)
