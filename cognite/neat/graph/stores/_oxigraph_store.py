import logging
import os
import shutil
import time
from pathlib import Path

from rdflib import Graph, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.utils.auxiliary import local_import

from ._base import MIMETypes, NeatGraphStoreBase


class OxiGraphStore(NeatGraphStoreBase):
    """OxiGraph is a class that stores the graph using OxiGraph and provides methods to read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        base_prefix : Used as a base prefix for graph namespace, allowing querying graph data using a shortform of a URI
        namespace : Namespace (aka URI) used to resolve any relative URI in the graph
        prefixes : Dictionary of additional prefixes used and bounded to the graph
    """

    rdf_store_type = "oxigraph"

    def __init__(
        self,
        graph: Graph | None = None,
        base_prefix: str = "",  # usually empty
        namespace: Namespace = DEFAULT_NAMESPACE,
        prefixes: dict = PREFIXES,
    ):
        super().__init__(graph, base_prefix, namespace, prefixes)

    def _set_graph(self) -> None:
        logging.info("Initializing Oxigraph store")
        local_import("pyoxigraph", "oxi")
        import pyoxigraph

        from cognite.neat.graph.stores import _oxrdflib

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
        else:
            raise Exception("Error initializing Oxigraph store")

        self.graph = Graph(store=_oxrdflib.OxigraphStore(store=oxstore))
        self.graph.default_union = True
        self.garbage_collector()

    def close(self):
        """Closes the graph."""
        if self.graph:
            try:
                self.graph.store._inner.flush()  # type: ignore[attr-defined]
                self.graph.close(True)
            except Exception as e:
                logging.debug("Error closing graph: %s", e)

    def restart(self):
        """Restarts the graph"""
        self.close()
        self.reinit_graph()
        logging.info("GraphStore restarted")

    def import_from_file(
        self, graph_file: Path, mime_type: MIMETypes = "application/rdf+xml", add_base_iri: bool = True
    ) -> None:
        """Imports graph data from file.

        Args:
            graph_file : File path to file containing graph data, by default None
            mime_type : MIME type of the file, by default "application/rdf+xml"
            add_base_iri : Add base IRI to the graph, by default True
        """
        if add_base_iri:
            self.graph.store._inner.bulk_load(  # type: ignore[attr-defined]
                str(graph_file), mime_type, base_iri=self.namespace
            )
        else:
            self.graph.store._inner.bulk_load(str(graph_file), mime_type)  # type: ignore[attr-defined]
        self.graph.store._inner.optimize()  # type: ignore[attr-defined]
        return None

    def drop(self):
        try:
            self.close()
            # Due to the specifics of Oxigraph, storage directory cannot be deleted immediately
            # after closing the graph and creating a new one
            if self.internal_storage_dir.exists():
                self.storage_dirs_to_delete.append(self.internal_storage_dir)
            self.internal_storage_dir = Path(str(self.internal_storage_dir_orig) + "_" + str(time.time()))

        except Exception as e:
            logging.error(f"Error dropping graph : {e}")

    def garbage_collector(self):
        """Garbage collection of the graph store."""
        # delete all directories in self.storage_dirs_to_delete
        for d in self.storage_dirs_to_delete:
            shutil.rmtree(d)
        self.storage_dirs_to_delete = []

    def __del__(self):
        if self.graph:
            if self.graph.store:
                self.graph.store._inner.flush()
            self.graph.close()
        # It requires more investigation os.remove(self.internal_storage_dir / "LOCK")

    def commit(self):
        """Commits the graph."""
        if self.graph:
            if self.graph.store:
                logging.info("Committing graph - flushing and optimizing")
                self.graph.store._inner.flush()
                self.graph.store._inner.optimize()
            self.graph.commit()

    @staticmethod
    def drop_graph_store_storage(storage_path: Path | None) -> None:
        """Drop graph store storage on disk.

        Args:
            storage_path : Path to storage directory
        """
        if storage_path and storage_path.exists():
            for f in os.listdir(storage_path):
                (storage_path / f).unlink()
            logging.info("Graph store dropped.")
        else:
            logging.info(f"Storage path {storage_path} does not exist. Skipping drop.")
