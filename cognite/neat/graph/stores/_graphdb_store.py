import logging

import requests
from rdflib import Graph, Namespace
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES

from ._base import NeatGraphStoreBase


class GraphDBStore(NeatGraphStoreBase):
    """GraphDB is a class that stores the graph in a GraphDB instances and provides methods to
    read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        base_prefix : Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
        namespace : Namespace (aka URI) used to resolve any relative URI in the graph
        prefixes : Dictionary of additional prefixes used and bounded to the graph
    """

    rdf_store_type = "graphdb"

    def __init__(
        self,
        graph: Graph | None = None,
        base_prefix: str = "",  # usually empty
        namespace: Namespace = DEFAULT_NAMESPACE,
        prefixes: dict = PREFIXES,
    ):
        super().__init__(graph, base_prefix, namespace, prefixes)
        self.graph_db_rest_url: str = "http://localhost:7200"

    def _set_graph(self) -> None:
        logging.info("Initializing graph store with GraphDB")
        store = SPARQLUpdateStore(
            query_endpoint=self.rdf_store_query_url,
            update_endpoint=self.rdf_store_update_url,
            returnFormat=self.returnFormat,
            context_aware=False,
            postAsEncoded=False,
            autocommit=False,
        )
        self.graph = Graph(store=store)

    def drop(self):
        """Drops the graph."""
        r = requests.delete(f"{self.rdf_store_query_url}/rdf-graphs/service?default")
        logging.info(f"Dropped graph with state: {r.text}")
