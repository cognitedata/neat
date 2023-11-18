import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import TypeAlias

import pandas as pd
import requests
from prometheus_client import Gauge, Summary
from rdflib import Graph, Literal, Namespace
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from rdflib.query import Result
from rdflib.term import URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.graph.extractors.rdf_to_graph import rdf_file_to_graph
from cognite.neat.graph.stores.configuration import RdfStoreType
from cognite.neat.rules.models.rules import Rules
from cognite.neat.utils.auxiliary import local_import

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

prom_qsm = Summary("store_query_time_summary", "Time spent processing queries", ["query"])
prom_sq = Gauge("store_single_query_time", "Time spent processing a single query", ["query"])
Triple: TypeAlias = tuple[URIRef, URIRef, Literal | URIRef]


class NeatGraphStore:
    """NeatGraphStore is a class that stores the graph and provides methods to read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        base_prefix : Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
        namespace : Namespace (aka URI) used to resolve any relative URI in the graph
        prefixes : Dictionary of additional prefixes used in the graph
    """

    def __init__(
        self,
        graph: Graph | None = None,
        base_prefix: str = "",  # usually empty
        namespace: Namespace = DEFAULT_NAMESPACE,
        prefixes: dict = PREFIXES,
    ):
        self.graph = graph or Graph()
        self.base_prefix: str = base_prefix
        self.namespace: Namespace = namespace
        self.prefixes: dict[str, Namespace] = prefixes

        self.rdf_store_type: str = RdfStoreType.MEMORY
        self.rdf_store_query_url: str | None = None
        self.rdf_store_update_url: str | None = None
        self.returnFormat: str | None = None
        self.df_cache: pd.DataFrame | None = None
        self.graph_db_rest_url: str = "http://localhost:7200"
        self.internal_storage_dir: Path | None = None
        self.graph_name: str | None = None
        self.internal_storage_dir_orig: Path | None = None
        self.storage_dirs_to_delete: list[Path] = []

    @classmethod
    def from_rules(cls, rules: Rules) -> Self:
        """
        Creates a new instance of NeatGraphStore from TransformationRules and runs the .init_graph() method on it.

        Args:
            rules: TransformationRules object containing information about the graph store.

        Returns:
            An instantiated instance of NeatGraphStore

        """
        if rules.metadata.namespace is None:
            namespace = DEFAULT_NAMESPACE
        else:
            namespace = rules.metadata.namespace
        store = cls(prefixes=rules.prefixes, namespace=namespace)
        store.init_graph(base_prefix=rules.metadata.prefix)
        return store

    def init_graph(
        self,
        rdf_store_type: str = RdfStoreType.MEMORY,
        rdf_store_query_url: str | None = None,
        rdf_store_update_url: str | None = None,
        graph_name: str | None = None,
        base_prefix: str | None = None,
        returnFormat: str = "csv",
        internal_storage_dir: Path | None = None,
    ):
        """Initializes the graph.

        Args:
            rdf_store_type : Graph store type, by default RdfStoreType.MEMORY
            rdf_store_query_url : URL towards which SPARQL query is executed, by default None
            rdf_store_update_url : URL towards which SPARQL update is executed, by default None
            graph_name : Name of graph, by default None
            base_prefix : Base prefix for graph namespace to change if needed, by default None
            returnFormat : Transport format of graph data between, by default "csv"
            internal_storage_dir : Path to directory where internal storage is located,
                                   by default None (in-memory storage).

        !!! note "internal_storage_dir"
            Used only for Oxigraph
        """
        logging.info("Initializing NeatGraphStore")
        self.rdf_store_type = rdf_store_type
        self.rdf_store_query_url = rdf_store_query_url
        self.rdf_store_update_url = rdf_store_update_url
        self.graph_name = graph_name
        self.returnFormat = returnFormat
        self.internal_storage_dir = Path(internal_storage_dir) if internal_storage_dir else None
        self.internal_storage_dir_orig = (
            self.internal_storage_dir if self.internal_storage_dir_orig is None else self.internal_storage_dir_orig
        )

        if self.rdf_store_type in ["", RdfStoreType.MEMORY]:
            logging.info("Initializing graph in memory")
            self.graph = Graph()
        elif self.rdf_store_type == RdfStoreType.OXIGRAPH:
            logging.info("Initializing Oxigraph store")
            local_import("pyoxigraph", "oxi")
            import pyoxigraph

            from cognite.neat.graph.stores import oxrdflib

            # Adding support for both in-memory and file-based storage
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
                    else:
                        raise e

            self.graph = Graph(store=oxrdflib.OxigraphStore(store=oxstore))
            self.graph.default_union = True
            self.garbage_collector()

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
        logging.info("Adding prefix %s with namespace %s", self.base_prefix, self.namespace)
        logging.info("Graph initialized")

    def reinit_graph(self):
        """Reinitializes the graph."""
        self.init_graph(
            self.rdf_store_type,
            self.rdf_store_query_url,
            self.rdf_store_update_url,
            self.graph_name,
            self.base_prefix,
            self.returnFormat,
            self.internal_storage_dir,
        )

    def close(self):
        """Closes the graph."""
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            try:
                if self.graph:
                    self.graph.store._inner.flush()  # type: ignore[attr-defined]
                    self.graph.close(True)
            except Exception as e:
                logging.debug("Error closing graph: %s", e)

    def restart(self):
        """Restarts the graph"""
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            self.close()
            self.reinit_graph()
            logging.info("GraphStore restarted")

    def import_from_file(self, graph_file: Path, mime_type: str = "application/rdf+xml", add_base_iri: bool = True):
        """Imports graph data from file.

        Args:
            graph_file : File path to file containing graph data, by default None
        """

        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            if add_base_iri:
                self.graph.store._inner.bulk_load(  # type: ignore[attr-defined]
                    str(graph_file), mime_type, base_iri=self.namespace
                )
            else:
                self.graph.store._inner.bulk_load(str(graph_file), mime_type)  # type: ignore[attr-defined]
            self.graph.store._inner.optimize()  # type: ignore[attr-defined]
        else:
            if add_base_iri:
                self.graph = rdf_file_to_graph(graph_file, base_namespace=self.namespace, prefixes=self.prefixes)
            else:
                self.graph = rdf_file_to_graph(graph_file, prefixes=self.prefixes)
        return

    def get_graph(self) -> Graph:
        """Returns the graph."""
        return self.graph

    def set_graph(self, graph: Graph):
        """Sets the graph."""
        self.graph = graph

    def query(self, query: str) -> Result:
        """Returns the result of the query."""
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
            self.reinit_graph()
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            try:
                self.close()
                # Due to the specifics of Oxigraph, storage directory cannot be deleted immediately
                # after closing the graph and creating a new one
                if self.internal_storage_dir.exists():
                    self.storage_dirs_to_delete.append(self.internal_storage_dir)
                self.internal_storage_dir = Path(str(self.internal_storage_dir_orig) + "_" + str(time.time()))

            except Exception as e:
                logging.error(f"Error dropping graph : {e}")

        elif self.rdf_store_type == RdfStoreType.GRAPHDB:
            r = requests.delete(f"{self.graph_db_rest_url}/repositories/{self.graph_name}/rdf-graphs/service?default")
            logging.info(f"Dropped graph with state: {r.text}")

    def garbage_collector(self):
        """Garbage collection of the graph store."""
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            # delete all directoreis in self.storage_dirs_to_delete
            for d in self.storage_dirs_to_delete:
                shutil.rmtree(d)
            self.storage_dirs_to_delete = []

    def query_to_dataframe(
        self,
        query: str,
        column_mapping: dict | None = None,
        save_to_cache: bool = False,
        index_column: str = "instance",
    ) -> pd.DataFrame:
        """Returns the result of the query as a dataframe.

        Args:
            query: SPARQL query to execute
            column_mapping: Columns name mapping, by default None
            save_to_cache: Save result of query to cache, by default False
            index_column: Indexing column , by default "instance"

        Returns:
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
            if self.graph:
                if self.graph.store:
                    self.graph.store._inner.flush()
                self.graph.close()
            # It requires more investigation os.remove(self.internal_storage_dir / "LOCK")

    def commit(self):
        """Commits the graph."""
        if self.rdf_store_type == RdfStoreType.OXIGRAPH:
            if self.graph:
                if self.graph.store:
                    logging.info("Committing graph - flushing and optimizing")
                    self.graph.store._inner.flush()
                    self.graph.store._inner.optimize()
        self.graph.commit()

    def get_df(self) -> pd.DataFrame:
        """Returns the cached dataframe."""
        if self.df_cache is None:
            raise ValueError("Cache is empty. Run query_to_dataframe() first with save_to_cache.")
        return self.df_cache

    def get_instance_properties_from_cache(self, instance_id: str) -> pd.DataFrame:
        """Returns the properties of an instance."""
        if self.df_cache is None:
            raise ValueError("Cache is empty. Run query_to_dataframe() first with save_to_cache.")
        return self.df_cache.loc[self.df_cache["instance"] == instance_id]

    def print_triples(self):
        """Prints the triples of the graph."""
        for subj, pred, obj in self.graph:
            logging.info(f"Triple: {subj} {pred} {obj}")

    def add_triples(self, triples: list[Triple], batch_size: int = 10_000, verbose: bool = False):
        """Adds triples to the graph store in batches.

        Args:
            triples: list of triples to be added to the graph store
            batch_size: Batch size of triples per commit, by default 10_000
            verbose: Verbose mode, by default False
        """

        commit_counter = 0
        if verbose:
            logging.info(f"Committing total of {len(triples)} triples to knowledge graph!")
        total_number_of_triples = len(triples)
        number_of_uploaded_triples = 0

        def check_commit(force_commit: bool = False):
            """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
            nonlocal commit_counter
            nonlocal number_of_uploaded_triples
            if force_commit:
                number_of_uploaded_triples += commit_counter
                self.graph.commit()
                if verbose:
                    logging.info(f"Committed {number_of_uploaded_triples} of {total_number_of_triples} triples")
                return
            commit_counter += 1
            if commit_counter >= batch_size:
                number_of_uploaded_triples += commit_counter
                self.graph.commit()
                if verbose:
                    logging.info(f"Committed {number_of_uploaded_triples} of {total_number_of_triples} triples")
                commit_counter = 0

        for triple in triples:
            self.graph.add(triple)
            check_commit()

        check_commit(force_commit=True)


def drop_graph_store_storage(rdf_store_type: str, storage_path: Path | None, force: bool = False):
    """Drop graph store storage on disk.

    Args:
        graph : Instance of NeatGraphStore
        storage_path : Path to storage directory
        force : Forcefully drop of graph. Defaults to False.
    """
    if rdf_store_type == RdfStoreType.OXIGRAPH and storage_path:
        if storage_path.exists():
            for f in os.listdir(storage_path):
                (storage_path / f).unlink()
            logging.info("Graph store dropped.")
        else:
            logging.info(f"Storage path {storage_path} does not exist. Skipping drop.")
    else:
        logging.info(f"Graph store {rdf_store_type} is not Oxigraph or storage path is not provided. Skipping drop.")
