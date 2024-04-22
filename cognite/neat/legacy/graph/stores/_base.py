import logging
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal, TypeAlias, cast

import pandas as pd
from prometheus_client import Gauge, Summary
from rdflib import Graph, Namespace, URIRef
from rdflib.query import Result, ResultRow

from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.legacy.graph.models import Triple
from cognite.neat.legacy.graph.stores._rdf_to_graph import rdf_file_to_graph
from cognite.neat.legacy.rules.models.rules import Rules

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

prom_qsm = Summary("store_query_time_summary_legacy", "Time spent processing queries", ["query"])
prom_sq = Gauge("store_single_query_time_legacy", "Time spent processing a single query", ["query"])

MIMETypes: TypeAlias = Literal[
    "application/rdf+xml", "text/turtle", "application/n-triple", "application/n-quads", "application/trig"
]


class NeatGraphStoreBase(ABC):
    """NeatGraphStore is a class that stores the graph and provides methods to read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        base_prefix : Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
        namespace : Namespace (aka URI) used to resolve any relative URI in the graph
        prefixes : Dictionary of additional prefixes used and bounded to the graph
    """

    rdf_store_type: str

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

        self.rdf_store_query_url: str | None = None
        self.rdf_store_update_url: str | None = None
        self.returnFormat: str | None = None
        self.df_cache: pd.DataFrame | None = None
        self.internal_storage_dir: Path | None = None
        self.graph_name: str | None = None
        self.internal_storage_dir_orig: Path | None = None
        self.storage_dirs_to_delete: list[Path] = []
        self.queries = _Queries(self)

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

    @abstractmethod
    def _set_graph(self) -> None:
        raise NotImplementedError()

    def init_graph(
        self,
        rdf_store_query_url: str | None = None,
        rdf_store_update_url: str | None = None,
        graph_name: str | None = None,
        base_prefix: str | None = None,
        returnFormat: str = "csv",
        internal_storage_dir: Path | None = None,
    ):
        """Initializes the graph.

        Args:
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
        self.rdf_store_query_url = rdf_store_query_url
        self.rdf_store_update_url = rdf_store_update_url
        self.graph_name = graph_name
        self.returnFormat = returnFormat
        self.internal_storage_dir = Path(internal_storage_dir) if internal_storage_dir else None
        self.internal_storage_dir_orig = (
            self.internal_storage_dir if self.internal_storage_dir_orig is None else self.internal_storage_dir_orig
        )

        self._set_graph()

        if self.prefixes:
            for prefix, namespace in self.prefixes.items():
                logging.info("Adding prefix %s with namespace %s", prefix, namespace)
                self.graph.bind(prefix, namespace)

        if base_prefix:
            self.base_prefix = base_prefix

        self.graph.bind(self.base_prefix, self.namespace)
        logging.info("Adding prefix %s with namespace %s", self.base_prefix, self.namespace)
        logging.info("Graph initialized")

    def reinitialize_graph(self):
        """Reinitialize the graph."""
        self.init_graph(
            self.rdf_store_query_url,
            self.rdf_store_update_url,
            self.graph_name,
            self.base_prefix,
            self.returnFormat,
            self.internal_storage_dir,
        )

    def upsert_prefixes(self, prefixes: dict[str, Namespace]) -> None:
        """Adds prefixes to the graph store."""
        self.prefixes.update(prefixes)
        for prefix, namespace in prefixes.items():
            logging.info("Adding prefix %s with namespace %s", prefix, namespace)
            self.graph.bind(prefix, namespace)

    def close(self) -> None:
        """Closes the graph."""
        # Can be overridden in subclasses
        return None

    def restart(self) -> None:
        """Restarts the graph"""
        # Can be overridden in subclasses
        return None

    def import_from_file(
        self, graph_file: Path, mime_type: MIMETypes = "application/rdf+xml", add_base_iri: bool = True
    ) -> None:
        """Imports graph data from file.

        Args:
            graph_file : File path to file containing graph data, by default None
            mime_type : MIME type of graph data, by default "application/rdf+xml"
            add_base_iri : Add base IRI to graph, by default True
        """
        if add_base_iri:
            self.graph = rdf_file_to_graph(
                self.graph, graph_file, base_namespace=self.namespace, prefixes=self.prefixes
            )
        else:
            self.graph = rdf_file_to_graph(self.graph, graph_file, prefixes=self.prefixes)
        return None

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

    def serialize(self, *args, **kwargs):
        """Serializes the graph."""
        return self.graph.serialize(*args, **kwargs)

    def query_delayed(self, query) -> Iterable[Triple]:
        """Returns the result of the query, but does not execute it immediately.

        The query is not executed until the result is iterated over.

        Args:
            query: SPARQL query to execute

        Returns:
            An iterable of triples

        """
        return _DelayedQuery(self.graph, query)

    @abstractmethod
    def drop(self) -> None:
        """Drops the graph."""
        raise NotImplementedError()

    def garbage_collector(self) -> None:
        """Garbage collection of the graph store."""
        # Can be overridden in subclasses
        return None

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

    def commit(self):
        """Commits the graph."""
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

    def diagnostic_report(self):
        """Returns the dictionary representation graph diagnostic data ."""
        return {
            "rdf_store_type": self.rdf_store_type,
            "base_prefix": self.base_prefix,
            "namespace": self.namespace,
            "prefixes": self.prefixes,
            "internal_storage_dir": self.internal_storage_dir,
            "rdf_store_query_url": self.rdf_store_query_url,
            "rdf_store_update_url": self.rdf_store_update_url,
        }

    def add_triples(self, triples: list[Triple] | set[Triple], batch_size: int = 10_000, verbose: bool = False):
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


class _DelayedQuery(Iterable):
    def __init__(self, graph_ref: Graph, query: str):
        self.graph_ref = graph_ref
        self.query = query

    def __iter__(self) -> Iterator[Triple]:
        start_time = time.perf_counter()
        result = self.graph_ref.query(self.query)
        stop_time = time.perf_counter()
        elapsed_time = stop_time - start_time
        prom_qsm.labels("query").observe(elapsed_time)
        prom_sq.labels("query").set(elapsed_time)
        return cast(Iterator[Triple], iter(result))


class _Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(self, store: NeatGraphStoreBase):
        self.store = store

    def list_instances_ids_of_class(self, class_uri: URIRef, limit: int = -1) -> list[URIRef]:
        """Get instances ids for a given class

        Args:
            class_uri: Class for which instances are to be found
            limit: Max number of instances to return, by default -1 meaning all instances

        Returns:
            List of class instance URIs
        """
        query_statement = "SELECT DISTINCT ?subject WHERE { ?subject a <class> .} LIMIT X".replace(
            "class", class_uri
        ).replace("LIMIT X", "" if limit == -1 else f"LIMIT {limit}")
        return [cast(tuple, res)[0] for res in list(self.store.query(query_statement))]

    def list_instances_of_type(self, class_uri: URIRef) -> list[ResultRow]:
        """Get all triples for instances of a given class

        Args:
            class_uri: Class for which instances are to be found

        Returns:
            List of triples for instances of the given class
        """
        query = (
            f"SELECT ?instance ?prop ?value "
            f"WHERE {{ ?instance rdf:type <{class_uri}> . ?instance ?prop ?value . }} order by ?instance "
        )
        logging.info(query)
        # Select queries gives an iterable of result rows
        return cast(list[ResultRow], list(self.store.query(query)))
