import sys
import warnings
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast

import pytz
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from rdflib.query import ResultRow

from cognite.neat.graph._shared import MIMETypes
from cognite.neat.graph.extractors import RdfFileExtractor, TripleExtractors
from cognite.neat.graph.models import Triple
from cognite.neat.rules.models.information import InformationRules
from cognite.neat.utils import remove_namespace
from cognite.neat.utils.auxiliary import local_import

from ._provenance import Change, Provenance

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class NeatGraphStore:
    """NeatGraphStore is a class that stores the graph and provides methods to read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        rules:
    """

    rdf_store_type: str

    def __init__(
        self,
        graph: Graph,
        rules: InformationRules | None = None,
    ):
        _start = datetime.now(pytz.utc)
        self.graph = graph
        self.provenance = Provenance(
            [
                Change.record(
                    activity=f"{type(self).__name__}.__init__",
                    start=_start,
                    end=datetime.now(pytz.utc),
                    description=f"Initialize graph store as {type(self.graph.store).__name__}",
                )
            ]
        )
        self.rules = rules

        if self.rules and self.rules.prefixes:
            self._upsert_prefixes(self.rules.prefixes)

        self.queries = _Queries(self)

    def _upsert_prefixes(self, prefixes: dict[str, Namespace]) -> None:
        """Adds prefixes to the graph store."""
        _start = datetime.now(pytz.utc)
        for prefix, namespace in prefixes.items():
            self.graph.bind(prefix, namespace)

        self.provenance.append(
            Change.record(
                activity=f"{type(self).__name__}._upsert_prefixes",
                start=_start,
                end=datetime.now(pytz.utc),
                description="Upsert prefixes to graph store",
            )
        )

    @classmethod
    def from_memory_store(cls, rules: InformationRules | None = None) -> "Self":
        return cls(Graph(), rules)

    @classmethod
    def from_sparql_store(
        cls,
        query_endpoint: str | None = None,
        update_endpoint: str | None = None,
        returnFormat: str = "csv",
        rules: InformationRules | None = None,
    ) -> "Self":
        store = SPARQLUpdateStore(
            query_endpoint=query_endpoint,
            update_endpoint=update_endpoint,
            returnFormat=returnFormat,
            context_aware=False,
            postAsEncoded=False,
            autocommit=False,
        )
        graph = Graph(store=store)
        return cls(graph, rules)

    @classmethod
    def from_oxi_store(cls, storage_dir: Path | None = None, rules: InformationRules | None = None) -> "Self":
        """Creates a NeatGraphStore from an Oxigraph store."""
        local_import("pyoxigraph", "oxi")
        import pyoxigraph

        from cognite.neat.graph.stores._oxrdflib import OxigraphStore

        # Adding support for both oxigraph in-memory and file-based storage
        for i in range(4):
            try:
                oxi_store = pyoxigraph.Store(path=str(storage_dir) if storage_dir else None)
                break
            except OSError as e:
                if "lock" in str(e) and i < 3:
                    continue
                raise e
        else:
            raise Exception("Error initializing Oxigraph store")

        graph = Graph(store=OxigraphStore(store=oxi_store))
        graph.default_union = True

        return cls(graph, rules)

    def write(self, extractor: TripleExtractors) -> None:
        if isinstance(extractor, RdfFileExtractor):
            self._parse_file(extractor.filepath, extractor.mime_type, extractor.base_uri)
        else:
            self._add_triples(extractor.extract())

    def _parse_file(
        self,
        filepath: Path,
        mime_type: MIMETypes = "application/rdf+xml",
        base_uri: URIRef | None = None,
    ) -> None:
        """Imports graph data from file.

        Args:
            filepath : File path to file containing graph data, by default None
            mime_type : MIME type of graph data, by default "application/rdf+xml"
            add_base_iri : Add base IRI to graph, by default True
        """

        # Oxigraph store, do not want to type hint this as it is an optional dependency
        if type(self.graph.store).__name__ == "OxigraphStore":

            def parse_to_oxi_store():
                local_import("pyoxigraph", "oxi")
                from cognite.neat.graph.stores._oxrdflib import OxigraphStore

                cast(OxigraphStore, self.graph.store)._inner.bulk_load(str(filepath), mime_type, base_iri=base_uri)  # type: ignore[attr-defined]
                cast(OxigraphStore, self.graph.store)._inner.optimize()  # type: ignore[attr-defined]

            parse_to_oxi_store()

        # All other stores
        else:
            if filepath.is_file():
                self.graph.parse(filepath, publicID=base_uri)
            else:
                for filename in filepath.iterdir():
                    if filename.is_file():
                        self.graph.parse(filename, publicID=base_uri)

    def _add_triples(self, triples: Iterable[Triple], batch_size: int = 10_000):
        """Adds triples to the graph store in batches.

        Args:
            triples: list of triples to be added to the graph store
            batch_size: Batch size of triples per commit, by default 10_000
            verbose: Verbose mode, by default False
        """

        commit_counter = 0
        number_of_written_triples = 0

        def check_commit(force_commit: bool = False):
            """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
            nonlocal commit_counter
            nonlocal number_of_written_triples
            if force_commit:
                number_of_written_triples += commit_counter
                self.graph.commit()
                return
            commit_counter += 1
            if commit_counter >= batch_size:
                number_of_written_triples += commit_counter
                self.graph.commit()
                commit_counter = 0

        for triple in triples:
            self.graph.add(triple)
            check_commit()

        check_commit(force_commit=True)


class _Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(self, store: NeatGraphStore):
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
        return [cast(tuple, res)[0] for res in list(self.store.graph.query(query_statement))]

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

        # Select queries gives an iterable of result rows
        return cast(list[ResultRow], list(self.store.graph.query(query)))

    def triples_of_type_instances(self, rdf_type: str) -> list[tuple[str, str, str]]:
        """Get all triples of a given type.

        This method assumes the graph has been transformed into the default namespace.
        """

        if self.store.rules:
            query = (
                f"SELECT ?instance ?prop ?value "
                f"WHERE {{ ?instance a <{self.store.rules.metadata.namespace[rdf_type]}> . ?instance ?prop ?value . }} "
                "order by ?instance"
            )

            result = self.store.graph.query(query)

            # We cannot include the RDF.type in case there is a neat:type property
            return [remove_namespace(*triple) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index]
        else:
            warnings.warn("No rules found for the graph store, returning empty list.", stacklevel=2)
            return []
