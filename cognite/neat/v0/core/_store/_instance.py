import sys
import warnings
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast, overload
from zipfile import ZipExtFile

import pandas as pd
from pandas import Index
from rdflib import Dataset, Graph, Namespace, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._instances._shared import quad_formats, rdflib_to_oxi_type
from cognite.neat.v0.core._instances.extractors import RdfFileExtractor, TripleExtractors
from cognite.neat.v0.core._instances.queries import Queries
from cognite.neat.v0.core._instances.transformers import Transformers
from cognite.neat.v0.core._issues import IssueList, catch_issues
from cognite.neat.v0.core._issues.errors import NeatValueError, OxigraphStorageLockedError
from cognite.neat.v0.core._shared import InstanceType, Triple
from cognite.neat.v0.core._utils.auxiliary import local_import
from cognite.neat.v0.core._utils.rdf_ import (
    add_triples_in_batch,
    remove_namespace_from_uri,
)
from cognite.neat.v0.core._utils.text import humanize_collection

from ._provenance import Change, Entity, Provenance

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class NeatInstanceStore:
    """NeatInstanceStore is a class that stores instances as triples and provides methods to read/write data it contains


    Args:
        dataset : Instance of rdflib.Dataset class for instance storage

    !!! note "Dataset"
        The store leverages a RDF dataset which is defined as a collection of RDF graphs
        where all but one are named graphs associated with URIRef (the graph name),
        and the unnamed default graph which is in context of rdflib library has an
        identifier URIRef('urn:x-rdflib:default').
    """

    rdf_store_type: str

    def __init__(
        self,
        dataset: Dataset,
        default_named_graph: URIRef | None = None,
    ):
        _start = datetime.now(timezone.utc)
        self.dataset = dataset
        self.provenance = Provenance[Entity](
            [
                Change.record(
                    activity=f"{type(self).__name__}.__init__",
                    start=_start,
                    end=datetime.now(timezone.utc),
                    description=f"Initialize graph store as {type(self.dataset.store).__name__}",
                )
            ]
        )

        self.default_named_graph = default_named_graph or DATASET_DEFAULT_GRAPH_ID
        self.queries = Queries(self.dataset, self.default_named_graph)

    def graph(self, named_graph: URIRef | None = None) -> Graph:
        """Get named graph from the dataset to query over"""
        return self.dataset.graph(named_graph or self.default_named_graph)

    @property
    def type_(self) -> str:
        "Return type of the graph store"
        return type(self.dataset.store).__name__

    # no destination
    @overload
    def serialize(self, filepath: None = None) -> str: ...

    # with destination
    @overload
    def serialize(self, filepath: Path) -> None: ...

    def serialize(self, filepath: Path | None = None) -> None | str:
        """Serialize the graph store to a file.

        Args:
            filepath: File path to serialize the graph store to

        Returns:
            Serialized graph store

        !!! note "Trig Format"
            Notice that instead of turtle format we are using trig format for serialization.
            This is because trig format is a superset of turtle format and it allows us to
            serialize named graphs as well. Allowing serialization of one or more named graphs
            including the default graph.
        """
        if filepath:
            self.dataset.serialize(
                filepath,
                format="ox-trig" if self.type_ == "OxigraphStore" else "trig",
            )
            return None
        else:
            return self.dataset.serialize(format="ox-trig" if self.type_ == "OxigraphStore" else "trig")

    def _upsert_prefixes(self, prefixes: dict[str, Namespace], named_graph: URIRef) -> None:
        """Adds prefixes to the graph store."""
        _start = datetime.now(timezone.utc)
        for prefix, namespace in prefixes.items():
            self.graph(named_graph).bind(prefix, namespace)

        self.provenance.append(
            Change.record(
                activity=f"{type(self).__name__}._upsert_prefixes",
                start=_start,
                end=datetime.now(timezone.utc),
                description="Upsert prefixes to the name graph {named_graph}",
            )
        )

    @classmethod
    def from_memory_store(cls) -> "Self":
        return cls(Dataset())

    @classmethod
    def from_sparql_store(
        cls,
        query_endpoint: str | None = None,
        update_endpoint: str | None = None,
        returnFormat: str = "csv",
    ) -> "Self":
        store = SPARQLUpdateStore(
            query_endpoint=query_endpoint,
            update_endpoint=update_endpoint,
            returnFormat=returnFormat,
            context_aware=False,
            postAsEncoded=False,
            autocommit=False,
        )
        graph = Dataset(store=store)
        return cls(graph)

    @classmethod
    def from_oxi_remote_store(
        cls,
        remote_url: str,
        autocommit: bool = False,
    ) -> "Self":
        """Creates a NeatGraphStore from a remote Oxigraph store SPARQL endpoint."""

        return cls(
            dataset=Dataset(
                store=SPARQLUpdateStore(
                    query_endpoint=f"{remote_url}/query", update_endpoint=f"{remote_url}/update", autocommit=autocommit
                ),
                default_union=True,
            )
        )

    @classmethod
    def from_oxi_local_store(cls, storage_dir: Path | None = None) -> "Self":
        """Creates a NeatGraphStore from an Oxigraph store."""
        local_import("pyoxigraph", "oxi")
        local_import("oxrdflib", "oxi")
        import oxrdflib
        import pyoxigraph  # type: ignore[import-untyped]

        try:
            oxi_store = pyoxigraph.Store(path=str(storage_dir) if storage_dir else None)
        except OSError as e:
            if "lock" in str(e):
                raise OxigraphStorageLockedError(filepath=cast(Path, storage_dir)) from e
            raise e

        return cls(
            dataset=Dataset(
                store=oxrdflib.OxigraphStore(store=oxi_store),
            )
        )

    def write(self, extractor: TripleExtractors, named_graph: URIRef | None = None) -> IssueList:
        last_change: Change | None = None
        named_graph = named_graph or self.default_named_graph
        with catch_issues() as issue_list:
            _start = datetime.now(timezone.utc)
            success = True

            if isinstance(extractor, RdfFileExtractor) and not extractor.issue_list.has_errors:
                self._parse_file(
                    named_graph,
                    extractor.filepath,
                    cast(str, extractor.format),
                    extractor.base_uri,
                )
                if isinstance(extractor.filepath, ZipExtFile):
                    extractor.filepath.close()

            elif isinstance(extractor, RdfFileExtractor):
                success = False
                issue_text = "\n".join([issue.as_message() for issue in extractor.issue_list])
                warnings.warn(
                    (
                        f"Cannot write to named graph {named_graph} with "
                        f"{type(extractor).__name__}, errors found in file:\n{issue_text}"
                    ),
                    stacklevel=2,
                )
            else:
                self._add_triples(extractor.extract(), named_graph=named_graph)

            if success:
                _end = datetime.now(timezone.utc)
                # Need to do the hasattr in case the extractor comes from NeatEngine.
                activities = (
                    extractor._get_activity_names()
                    if hasattr(extractor, "_get_activity_names")
                    else [type(extractor).__name__]
                )
                for activity in activities:
                    last_change = Change.record(
                        activity=activity,
                        start=_start,
                        end=_end,
                        description=f"Extracted triples to named graph {named_graph} using {type(extractor).__name__}",
                    )
                    self.provenance.append(last_change)
        if last_change:
            last_change.target_entity.issues.extend(issue_list)
        return issue_list

    def read(
        self,
        class_uri: URIRef,
        named_graph: URIRef | None = None,
        property_renaming_config: dict[URIRef, str] | None = None,
        remove_uri_namespace: bool = True,
    ) -> Iterable[tuple[URIRef, dict[str | InstanceType, list[Any]]]]:
        named_graph = named_graph or self.default_named_graph

        instance_ids = self.queries.select.list_instances_ids(class_uri, named_graph=named_graph)

        for instance_id in instance_ids:
            if res := self.queries.select.describe(
                instance_id=instance_id,
                instance_type=class_uri,
                property_renaming_config=property_renaming_config,
                remove_uri_namespace=remove_uri_namespace,
            ):
                yield res

    def _parse_file(
        self,
        named_graph: URIRef,
        filepath: Path | ZipExtFile,
        format: str = "turtle",
        base_uri: URIRef | None = None,
    ) -> None:
        """Imports graph data from file.

        Args:
            named_graph : URIRef of the named graph to store the data in
            filepath : File path to file containing graph data, by default None
            format : rdflib format file containing RDF graph, by default "turtle"
            base_uri : base URI to add to graph in case of relative URIs, by default None

        !!! note "Oxigraph store"
            By default we are using non-transactional mode for parsing RDF files.
            This gives us a significant performance boost when importing large RDF files.
            Underhood of rdflib we are triggering oxrdflib plugin which in respect
            calls `bulk_load` method from oxigraph store. See more at:
            https://pyoxigraph.readthedocs.io/en/stable/store.html#pyoxigraph.Store.bulk_load
        """

        # Oxigraph store, do not want to type hint this as it is an optional dependency
        if self.type_ == "OxigraphStore":
            local_import("pyoxigraph", "oxi")

            if format in quad_formats():
                self.dataset.parse(
                    filepath,  # type: ignore[arg-type]
                    format=rdflib_to_oxi_type(format),
                    transactional=False,
                    publicID=base_uri,
                )
            else:
                self.graph(named_graph).parse(
                    filepath,  # type: ignore[arg-type]
                    format=rdflib_to_oxi_type(format),
                    transactional=False,
                    publicID=base_uri,
                )
            self.dataset.store._store.optimize()  # type: ignore[attr-defined]

        # All other stores
        else:
            if format in quad_formats():
                self.dataset.parse(filepath, publicID=base_uri, format=format)  # type: ignore[arg-type]
            else:
                self.graph(named_graph).parse(filepath, publicID=base_uri, format=format)  # type: ignore[arg-type]

    def _add_triples(
        self,
        triples: Iterable[Triple],
        named_graph: URIRef,
        batch_size: int = 10_000,
    ) -> None:
        """Adds triples to the graph store in batches.

        Args:
            triples: list of triples to be added to the graph store
            batch_size: Batch size of triples per commit, by default 10_000
            verbose: Verbose mode, by default False
        """
        add_triples_in_batch(self.graph(named_graph), triples, batch_size)

    def transform(self, transformer: Transformers, named_graph: URIRef | None = None) -> IssueList:
        """Transforms the graph store using a transformer."""
        named_graph = named_graph or self.default_named_graph
        issue_list = IssueList()
        if named_graph not in self.named_graphs:
            issue_list.append(NeatValueError(f"Named graph {named_graph} not found in graph store, cannot transform"))
            return issue_list
        if self.provenance.activity_took_place(type(transformer).__name__) and transformer._use_only_once:
            issue_list.append(
                NeatValueError(
                    f"Cannot transform graph store with {type(transformer).__name__}, already applied",
                )
            )
            return issue_list
        if missing_changes := [
            change for change in transformer._need_changes if not self.provenance.activity_took_place(change)
        ]:
            issue_list.append(
                NeatValueError(
                    f"Cannot transform graph store with {type(transformer).__name__}, "
                    f"missing one or more required changes {humanize_collection(missing_changes)}",
                )
            )
            return issue_list
        _start = datetime.now(timezone.utc)
        with catch_issues() as transform_issues:
            transformer.transform(self.graph(named_graph))
        issue_list.extend(transform_issues)
        self.provenance.append(
            Change.record(
                activity=f"{type(transformer).__name__}",
                start=_start,
                end=datetime.now(timezone.utc),
                description=transformer.description,
            )
        )
        return issue_list

    @property
    def summary(self) -> dict[URIRef, pd.DataFrame]:
        return {
            named_graph: pd.DataFrame(
                self.queries.select.summarize_instances(named_graph),
                columns=["Type", "Occurrence"],
            )
            for named_graph in self.named_graphs
        }

    @property
    def multi_type_instances(self) -> dict[URIRef, dict[str, list[str]]]:
        return {named_graph: self.queries.select.multi_type_instances(named_graph) for named_graph in self.named_graphs}

    def _repr_html_(self) -> str:
        provenance = self.provenance._repr_html_()
        summary: dict[URIRef, pd.DataFrame] = self.summary

        def _short_name_of_graph(named_graph: URIRef) -> str:
            return "default" if named_graph == self.default_named_graph else remove_namespace_from_uri(named_graph)

        if not summary:
            summary_text = "<br /><strong>Graph is empty</strong><br />"
        else:
            all_types = set().union(
                *[set(sub_summary.Type) for sub_summary in summary.values() if not sub_summary.empty]
            )

            summary_text = (
                "<br /><strong>Overview</strong>:"  # type: ignore
                f"<ul><li>{len(summary)} named graphs</strong></li>"
                f"<li>Total of {len(all_types)} unique types</strong></li>"
            )

            for named_graph, table in summary.items():
                summary_text += (
                    f"<li>{sum(table['Occurrence'])} instances in {_short_name_of_graph(named_graph)}"
                    " graph</strong></li>"
                )

            summary_text += "</ul>"
            for named_graph, table in summary.items():
                summary_text += (
                    f"<br /><strong>{_short_name_of_graph(named_graph)} graph</strong>:"
                    f"{cast(pd.DataFrame, self._shorten_summary(table))._repr_html_()}"  # type: ignore[operator]
                )

        for named_graph, multi_value_instances in self.multi_type_instances.items():
            if multi_value_instances:
                summary_text += (
                    f"<br><strong>Multi value instances detected in {_short_name_of_graph(named_graph)}"
                    "graph! Loading could have issues!</strong></br>"
                )

        return f"{summary_text}{provenance}"

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

    @property
    def named_graphs(self) -> list[URIRef]:
        return [cast(URIRef, context.identifier) for context in self.dataset.contexts()]

    @property
    def empty(self) -> bool:
        """Cheap way to check if the graph store is empty."""
        return not self.queries.select.has_data()

    def diff(self, current_named_graph: URIRef, new_named_graph: URIRef) -> None:
        """
        Compare two named graphs and store diff results in dedicated named graphs.

        Stores triples to add in DIFF_ADD and triples to delete in DIFF_DELETE.

        Args:
            current_named_graph: URI of the current named graph
            new_named_graph: URI of the new/updated named graph

        Raises:
            NeatValueError: If either named graph doesn't exist in the store
        """
        if current_named_graph not in self.named_graphs:
            raise NeatValueError(f"Current named graph not found: {current_named_graph}")
        if new_named_graph not in self.named_graphs:
            raise NeatValueError(f"New named graph not found: {new_named_graph}")

        # Clear previous diff results using SPARQL
        self.dataset.update(f"CLEAR SILENT GRAPH <{NAMED_GRAPH_NAMESPACE['DIFF_ADD']}>")
        self.dataset.update(f"CLEAR SILENT GRAPH <{NAMED_GRAPH_NAMESPACE['DIFF_DELETE']}>")

        # Store new diff results
        self._add_triples(
            self.queries.select.get_graph_diff(new_named_graph, current_named_graph),
            named_graph=NAMED_GRAPH_NAMESPACE["DIFF_ADD"],
        )
        self._add_triples(
            self.queries.select.get_graph_diff(current_named_graph, new_named_graph),
            named_graph=NAMED_GRAPH_NAMESPACE["DIFF_DELETE"],
        )
