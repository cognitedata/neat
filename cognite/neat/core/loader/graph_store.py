import logging
import shutil
import time
from pathlib import Path

import pandas as pd
import pyoxigraph
import requests
from prometheus_client import Gauge, Summary
from rdflib import Graph, Namespace
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from rdflib.query import Result

from cognite.neat.core.configuration import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.core.data_classes.config import RdfStoreType
from cognite.neat.core.data_stores import oxrdflib
from cognite.neat.core.loader.graph import rdf_file_to_graph

prom_qsm = Summary("store_query_time_summary", "Time spent processing queries", ["query"])
prom_sq = Gauge("store_single_query_time", "Time spent processing a single query", ["query"])


class NeatGraphStore:
    """NeatGraphStore is a class that stores the graph and provides methods to read/write data it contains


    Attributes
    ----------
    graph : Graph
        Instance of rdflib.Graph class for graph storage
    base_prefix : str
        Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
    namespace : Namespace
        Namespace (aka URI) used to resolve any relative URI in the graph
    prefixes : dict[str, URIRef]
        Dictionary of additional prefixes used in the graph
    """

    def __init__(
        self,
        graph: Graph = None,
        base_prefix: str = "",  # usually empty
        namespace: Namespace = DEFAULT_NAMESPACE,
        prefixes: dict = PREFIXES,
    ):
        self.graph: Graph = graph
        self.base_prefix: str = base_prefix
        self.namespace: Namespace = namespace
        self.prefixes: dict[str, Namespace] = prefixes

        self.rdf_store_type: str = RdfStoreType.MEMORY
        self.rdf_store_query_url: str = None
        self.rdf_store_update_url: str = None
        self.returnFormat: str = None
        self.df_cache: pd.DataFrame = None
        self.graph_db_rest_url: str = "http://localhost:7200"
        self.internal_storage_dir: Path = None

    def init_graph(
        self,
        rdf_store_type: str = RdfStoreType.MEMORY,
        rdf_store_query_url: str = None,
        rdf_store_update_url: str = None,
        graph_name: str = None,
        base_prefix: str = None,
        returnFormat: str = "csv",
        internal_storage_dir: Path = None,
    ):
        """Initializes the graph.

        Parameters
        ----------
        rdf_store_type : str, optional
            Graph store type, by default RdfStoreType.MEMORY
        rdf_store_query_url : str, optional
            URL towards which SPARQL query is executed, by default None
        rdf_store_update_url : str, optional
            URL towards which SPARQL update is executed, by default None
        graph_name : str, optional
            Name of graph, by default None
        base_prefix : str
            Base prefix for graph namespace to change if needed, by default None
        returnFormat : str, optional
            Transport format of graph data between, by default "csv"
        internal_storage_dir : Path, optional
            Path to directory where internal storage is located, by default None (in-memory storage). Used only for Oxigraph.
        """
        logging.info("Initializing NeatGraphStore")
        self.rdf_store_type = rdf_store_type
        self.rdf_store_query_url = rdf_store_query_url
        self.rdf_store_update_url = rdf_store_update_url
        self.graph_name = graph_name
        self.returnFormat = returnFormat
        self.internal_storage_dir = Path(internal_storage_dir) if internal_storage_dir else None

        if self.rdf_store_type in ["", RdfStoreType.MEMORY]:
            logging.info("Initializing graph in memory")
            self.graph = Graph()
        elif self.rdf_store_type == RdfStoreType.OXIGRAPH:
            logging.info("Initializing Oxigraph store")
            # Adding support for both in-memory and file-based storage
            oxstore = None
            for i in range(4):
                try:
                    oxstore = pyoxigraph.Store(
                        path=str(self.internal_storage_dir) if self.internal_storage_dir else None
                    )  # Store (Rust object) accepts only str as path and not Path.
                    break
                except OSError as e:
                    if "lock" in str(e) and i < 3:
                        # lock originated from another instance of the store
                        logging.error("Error initializing Oxigraph store: %s", e)
                        logging.info("Removing LOCK file and retrying")
                    else:
                        raise e

            self.graph = Graph(store=oxrdflib.OxigraphStore(store=oxstore))
            self.graph.default_union = True

        elif self.rdf_store_type == RdfStoreType.GRAPHDB:
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
        else:
            logging.error("Unknown RDF store type: %s", self.rdf_store_type)
            raise Exception("Unknown RDF store type: %s", self.rdf_store_type)

        if self.prefixes:
            for prefix, namespace in self.prefixes.items():
                logging.info("Adding prefix %s with namespace %s", prefix, namespace)
                self.graph.bind(prefix, namespace)

        if base_prefix:
            self.base_prefix = base_prefix

        self.graph.bind(self.base_prefix, self.namespace)
        logging.info("Graph initialized")

    def close(self):
        """Closes the graph."""
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            try:
                if self.graph:
                    self.graph.store._inner.flush()
                    self.graph.close()
            except Exception as e:
                logging.debug("Error closing graph: %s", e)

    def import_from_file(self, file_path: Path = None):
        """Imports graph data from file.

        Parameters
        ----------
        file_path : Path, optional
            File path to file containing graph data, by default None
        """

        if not file_path:
            file_path = self.config.rdf_import_path

        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            self.graph.store._inner.bulk_load(str(file_path), "application/rdf+xml", base_iri=self.namespace)
            self.graph.store._inner.optimize()
        else:
            self.graph = rdf_file_to_graph(file_path, base_namespace=self.namespace, prefixes=self.prefixes)
        return

    def get_graph(self) -> Graph:
        """Returns the graph."""
        return self.graph

    def set_graph(self, graph: Graph):
        """Sets the graph."""
        self.graph = graph

    def query(self, query: str) -> Result:
        """Returns the result of the query."""
        logging.info(f"Contexts: {list(self.graph.store.contexts())}")
        start_time = time.perf_counter()
        result = self.graph.query(query)
        stop_time = time.perf_counter()
        elapsed_time = stop_time - start_time
        prom_qsm.labels("query").observe(elapsed_time)
        prom_sq.labels("query").set(elapsed_time)
        return result

    def drop(self):
        """Drops the graph."""
        if self.rdf_store_type == RdfStoreType.MEMORY:
            # In case of in-memory graph, we just reinitialize the graph
            # otherwise we would lose the prefixes and bindings which fails
            # workflow
            self.init_graph(
                self.rdf_store_type,
                self.rdf_store_query_url,
                self.rdf_store_update_url,
                self.graph_name,
                self.base_prefix,
                self.returnFormat,
            )
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            self.graph.store._inner.clear()

        elif self.rdf_store_type == RdfStoreType.GRAPHDB:
            r = requests.delete(f"{self.graph_db_rest_url}/repositories/{self.graph_name}/rdf-graphs/service?default")
            logging.info("Dropped graph with state: %s", r.text)

    def query_to_dataframe(
        self,
        query: str,
        column_mapping: dict = None,
        save_to_cache: bool = False,
        index_column: str = "instance",
    ) -> pd.DataFrame:
        """Returns the result of the query as a dataframe.

        Parameters
        ----------
        query : str
            SPARQL query to execute
        column_mapping : dict, optional
            Columns name mapping, by default None
        save_to_cache : bool, optional
            Save result of query to cache, by default False
        index_column : str, optional
            Indexing column , by default "instance"

        Returns
        -------
        pd.DataFrame
            Dataframe with result of query
        """

        if column_mapping is None:
            column_mapping = {0: "instance", 1: "property", 2: "value"}

        result = self.graph.query(query, DEBUG=False)
        df_cache = pd.DataFrame(list(result))
        df_cache.rename(columns=column_mapping, inplace=True)
        df_cache[index_column] = df_cache[index_column].apply(lambda x: str(x))
        if save_to_cache:
            self.df_cache = df_cache
        return df_cache

    def __del__(self):
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            self.graph.store._inner.flush()
            self.graph.close()
            # It requires more investigation os.remove(self.internal_storage_dir / "LOCK")

    def get_df(self) -> pd.DataFrame:
        """Returns the cached dataframe."""
        return self.df_cache

    def get_instance_properties_from_cache(self, instance_id: str) -> pd.DataFrame:
        """Returns the properties of an instance."""
        return self.df_cache.loc[self.df_cache["instance"] == instance_id]


def drop_graph_store(graph: NeatGraphStore, storage_path: Path):
    """Drops graph store by flushing in-flight data , releasing locks and completly removing all files the storage path."""
    if graph:
        if graph.rdf_store_type == RdfStoreType.OXIGRAPH and storage_path:
            if storage_path.exists():
                graph.__del__()
                graph = None
                shutil.rmtree(storage_path)
