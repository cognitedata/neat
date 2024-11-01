import sys
import warnings
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pandas as pd
from pandas import Index
from rdflib import Graph, Namespace, URIRef
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors import RdfFileExtractor, TripleExtractors
from cognite.neat._graph.models import InstanceType, Triple
from cognite.neat._graph.queries import Queries
from cognite.neat._graph.transformers import Transformers
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models import InformationRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._utils.auxiliary import local_import

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

    @property
    def type_(self) -> str:
        "Return type of the graph store"
        return type(self.graph.store).__name__

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
        return cls(Graph(identifier=DEFAULT_NAMESPACE), rules)

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
        graph = Graph(store=store, identifier=DEFAULT_NAMESPACE)
        return cls(graph, rules)

    @classmethod
    def from_oxi_store(cls, storage_dir: Path | None = None, rules: InformationRules | None = None) -> "Self":
        """Creates a NeatGraphStore from an Oxigraph store."""
        local_import("pyoxigraph", "oxi")
        local_import("oxrdflib", "oxi")
        import oxrdflib
        import pyoxigraph

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

        graph = Graph(
            store=oxrdflib.OxigraphStore(store=oxi_store),
            identifier=DEFAULT_NAMESPACE,
        )

        return cls(graph, rules)

    def write(self, extractor: TripleExtractors) -> None:
        _start = datetime.now(timezone.utc)
        success = True

        if isinstance(extractor, RdfFileExtractor) and not extractor.issue_list.has_errors:
            self._parse_file(extractor.filepath, cast(str, extractor.mime_type), extractor.base_uri)
        elif isinstance(extractor, RdfFileExtractor):
            success = False
            issue_text = "\n".join([issue.as_message() for issue in extractor.issue_list])
            warnings.warn(
                f"Cannot write to graph store with {type(extractor).__name__}, errors found in file:\n{issue_text}",
                stacklevel=2,
            )
        else:
            self._add_triples(extractor.extract())

        if success:
            self.provenance.append(
                Change.record(
                    activity=f"{type(extractor).__name__}",
                    start=_start,
                    end=datetime.now(timezone.utc),
                    description=f"Extracted triples to graph store using {type(extractor).__name__}",
                )
            )

    def read(self, class_: str) -> Iterable[tuple[str, dict[str | InstanceType, list[str]]]]:
        """Read instances for given view from the graph store."""

        if not self.rules:
            warnings.warn("Rules not found in graph store!", stacklevel=2)
            return None

        class_entity = ClassEntity(prefix=self.rules.metadata.prefix, suffix=class_)

        if class_entity not in [definition.class_ for definition in self.rules.classes]:
            warnings.warn("Desired type not found in graph!", stacklevel=2)
            return None

        if not (class_uri := InformationAnalysis(self.rules).class_uri(class_entity)):
            warnings.warn(
                f"Class {class_} does not have namespace defined for prefix {class_entity.prefix} Rules!",
                stacklevel=2,
            )
            return None

        has_hop_transformations = InformationAnalysis(self.rules).has_hop_transformations()
        has_self_reference_transformations = InformationAnalysis(
            self.rules
        ).has_self_reference_property_transformations()
        if has_hop_transformations or has_self_reference_transformations:
            msg = (
                f"Rules contain [{'Hop' if has_hop_transformations else '' }"
                f", {'SelfReferenceProperty' if has_self_reference_transformations else '' }]"
                " rdfpath."
                f" Run [{'ReduceHopTraversal' if has_hop_transformations else '' }"
                f", {'AddSelfReferenceProperty' if has_self_reference_transformations else '' }]"
                " transformer(s) first!"
            )

            warnings.warn(
                msg,
                stacklevel=2,
            )
            return None

        # get all the instances for give class_uri
        instance_ids = self.queries.list_instances_ids_of_class(class_uri)

        # get potential property renaming config
        property_renaming_config = InformationAnalysis(self.rules).define_property_renaming_config(class_entity)

        # get property types to guide process of removing or not namespaces from results
        property_types = InformationAnalysis(self.rules).property_types(class_entity)

        for instance_id in instance_ids:
            if res := self.queries.describe(
                instance_id=instance_id,
                instance_type=class_,
                property_renaming_config=property_renaming_config,
                property_types=property_types,
            ):
                yield res

    def _parse_file(
        self,
        filepath: Path,
        mime_type: str = "application/rdf+xml",
        base_uri: URIRef | None = None,
    ) -> None:
        """Imports graph data from file.

        Args:
            filepath : File path to file containing graph data, by default None
            mime_type : MIME type of graph data, by default "application/rdf+xml"
            base_uri : Add base IRI to graph, by default True
        """

        # Oxigraph store, do not want to type hint this as it is an optional dependency
        if type(self.graph.store).__name__ == "OxigraphStore":

            def parse_to_oxi_store():
                local_import("pyoxigraph", "oxi")
                import pyoxigraph

                cast(pyoxigraph.Store, self.graph.store._store).bulk_load(
                    str(filepath),
                    mime_type,
                    base_iri=base_uri,
                    to_graph=pyoxigraph.NamedNode(self.graph.identifier),
                )
                cast(pyoxigraph.Store, self.graph.store._store).optimize()

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

    @property
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(self.queries.summarize_instances(), columns=["Type", "Occurrence"])

    def _repr_html_(self) -> str:
        provenance = self.provenance._repr_html_()
        summary: pd.DataFrame = self.summary

        if summary.empty:
            summary_text = "<br /><strong>Graph is empty</strong><br />"
        else:
            summary_text = (
                "<br /><strong>Overview</strong>:"  # type: ignore
                f"<ul><li>{len(summary)} types</strong></li>"
                f"<li>{sum(summary['Occurrence'])} instances</strong></li></ul>"
                f"{cast(pd.DataFrame, self._shorten_summary(summary))._repr_html_()}"  # type: ignore[operator]
            )

        return f"{summary_text}" f"{provenance}"

    def _shorten_summary(self, summary: pd.DataFrame) -> pd.DataFrame:
        """Shorten summary to top 5 types by occurrence."""
        top_5_rows = summary.head(5)

        indexes = [
            *top_5_rows.index.tolist(),
        ]
        data = [
            top_5_rows,
        ]
        if len(summary) > 6:
            last_row = summary.tail(1)
            indexes += [
                "...",
                *last_row.index.tolist(),
            ]
            data.extend([pd.DataFrame([["..."] * summary.shape[1]], columns=summary.columns), last_row])

        shorter_summary = pd.concat(
            data,
            ignore_index=True,
        )
        shorter_summary.index = cast(Index, indexes)

        return shorter_summary
