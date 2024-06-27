import sys
import warnings
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from rdflib import Graph, Namespace, URIRef
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph._shared import MIMETypes
from cognite.neat.graph.extractors import RdfFileExtractor, TripleExtractors
from cognite.neat.graph.models import Triple
from cognite.neat.graph.queries import Queries
from cognite.neat.graph.transformers import Transformers
from cognite.neat.rules.models import InformationRules
from cognite.neat.rules.models.entities import ClassEntity
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
        self.rules: InformationRules | None = None

        _start = datetime.now(timezone.utc)
        self.graph = graph
        self.provenance = Provenance(
            [
                Change.record(
                    activity=f"{type(self).__name__}.__init__",
                    start=_start,
                    end=datetime.now(timezone.utc),
                    description=f"Initialize graph store as {type(self.graph.store).__name__}",
                )
            ]
        )

        if rules:
            self.add_rules(rules)
        else:
            self.base_namespace = DEFAULT_NAMESPACE

        self.queries = Queries(self.graph, self.rules)

    def add_rules(self, rules: InformationRules) -> None:
        """This method is used to add rules to the graph store and it is the only correct
        way to add rules to the graph store, after the graph store has been initialized.
        """

        self.rules = rules
        self.base_namespace = self.rules.metadata.namespace
        self.queries = Queries(self.graph, self.rules)
        self.provenance.append(
            Change.record(
                activity=f"{type(self)}.rules",
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc),
                description=f"Added rules to graph store as {type(self.rules).__name__}",
            )
        )

        if self.rules.prefixes:
            self._upsert_prefixes(self.rules.prefixes)

    def _upsert_prefixes(self, prefixes: dict[str, Namespace]) -> None:
        """Adds prefixes to the graph store."""
        _start = datetime.now(timezone.utc)
        for prefix, namespace in prefixes.items():
            self.graph.bind(prefix, namespace)

        self.provenance.append(
            Change.record(
                activity=f"{type(self).__name__}._upsert_prefixes",
                start=_start,
                end=datetime.now(timezone.utc),
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
        _start = datetime.now(timezone.utc)

        if isinstance(extractor, RdfFileExtractor):
            self._parse_file(extractor.filepath, extractor.mime_type, extractor.base_uri)
        else:
            self._add_triples(extractor.extract())

        self.provenance.append(
            Change.record(
                activity=f"{type(extractor).__name__}",
                start=_start,
                end=datetime.now(timezone.utc),
                description=f"Extracted triples to graph store using {type(extractor).__name__}",
            )
        )

    def read(self, class_: str) -> list[tuple[str, str, str]]:
        """Read instances for given view from the graph store."""
        # PLACEHOLDER: Implement reading instances for a given view
        # not yet developed

        if not self.rules:
            warnings.warn(
                "No rules found for the graph store, returning empty list.",
                stacklevel=2,
            )
            return []

        class_entity = ClassEntity(prefix=self.rules.metadata.prefix, suffix=class_)

        if class_entity not in [definition.class_ for definition in self.rules.classes.data]:
            warnings.warn("Desired type not found in graph!", stacklevel=2)
            return []

        return self.queries.construct_instances_of_class(class_)

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

    def transform(self, transformer: Transformers) -> None:
        """Transforms the graph store using a transformer."""

        missing_changes = [
            change for change in transformer._need_changes if not self.provenance.activity_took_place(change)
        ]
        if self.provenance.activity_took_place(type(transformer).__name__) and transformer._use_only_once:
            warnings.warn(
                f"Cannot transform graph store with {type(transformer).__name__}, already applied",
                stacklevel=2,
            )
        elif missing_changes:
            warnings.warn(
                (
                    f"Cannot transform graph store with {type(transformer).__name__}, "
                    f"missing one or more required changes [{', '.join(missing_changes)}]"
                ),
                stacklevel=2,
            )

        else:
            _start = datetime.now(timezone.utc)
            transformer.transform(self.graph)
            self.provenance.append(
                Change.record(
                    activity=f"{type(transformer).__name__}",
                    start=_start,
                    end=datetime.now(timezone.utc),
                    description=transformer.description,
                )
            )

    def _repr_html_(self) -> str:
        provenance = self.provenance._repr_html_()

        return (
            f"<strong>{type(self).__name__}</strong> A graph store is a container for storing triples. "
            "It can be queried and transformed to extract information.<br />"
            "<strong>Provenance</strong> Provenance is a record of changes that have occurred in the graph store.<br />"
            f"{provenance}"
        )
