import sys
import warnings
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast, overload
from zipfile import ZipExtFile

import pandas as pd
from pandas import Index
from rdflib import Dataset, Graph, Namespace, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from cognite.neat._graph._shared import quad_formats, rdflib_to_oxi_type
from cognite.neat._graph.extractors import RdfFileExtractor, TripleExtractors
from cognite.neat._graph.queries import Queries
from cognite.neat._graph.transformers import Transformers
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import OxigraphStorageLockedError
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models import InformationRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._shared import InstanceType, Triple
from cognite.neat._utils.auxiliary import local_import
from cognite.neat._utils.rdf_ import add_triples_in_batch, remove_namespace_from_uri

from ._provenance import Change, Entity, Provenance

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class NeatGraphStore:
    """NeatGraphStore is a class that stores the graph and provides methods to read/write data it contains


    Args:
        graph : Instance of rdflib.Graph class for graph storage
        rules:

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
        self.rules: dict[URIRef, InformationRules] = {}
        self.base_namespace: dict[URIRef, Namespace] = {}

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

        self.queries = Queries(self.dataset, self.rules, self.default_named_graph)

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

    def add_rules(self, rules: InformationRules, named_graph: URIRef | None = None) -> None:
        """This method is used to add rules to a named graph stored in the graph store.

        Args:
            rules: InformationRules object containing rules to be added to the named graph
            named_graph: URIRef of the named graph to store the rules in, by default None
                        rules will be added to the default graph

        """

        named_graph = named_graph or self.default_named_graph

        if named_graph in self.named_graphs:
            # attaching appropriate namespace to the rules
            # as well base_namespace
            self.rules[named_graph] = rules
            self.base_namespace[named_graph] = rules.metadata.namespace
            self.queries = Queries(self.dataset, self.rules)
            self.provenance.append(
                Change.record(
                    activity=f"{type(self)}.rules",
                    start=datetime.now(timezone.utc),
                    end=datetime.now(timezone.utc),
                    description=f"Added {type(self.rules).__name__} to {named_graph} named graph",
                )
            )

            if self.rules[named_graph].prefixes:
                self._upsert_prefixes(self.rules[named_graph].prefixes, named_graph)

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
                    query_endpoint=f"{remote_url}/query", update_endpoint=f"{remote_url}/query", autocommit=autocommit
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
        import pyoxigraph

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

    def _read_via_rules_linkage(
        self,
        class_neat_id: URIRef,
        property_link_pairs: dict[str, URIRef] | None,
        named_graph: URIRef | None = None,
    ) -> Iterable[tuple[str, dict[str | InstanceType, list[str]]]]:
        named_graph = named_graph or self.default_named_graph

        if named_graph not in self.named_graphs:
            warnings.warn(
                f"Named graph {named_graph} not found in graph store, cannot read",
                stacklevel=2,
            )
            return

        if not self.rules or named_graph not in self.rules:
            warnings.warn(
                f"Rules for named graph {named_graph} not found in graph store!",
                stacklevel=2,
            )
            return

        if self.multi_type_instances:
            warnings.warn(
                "Multi typed instances detected, issues with loading can occur!",
                stacklevel=2,
            )

        analysis = InformationAnalysis(self.rules[named_graph])

        if cls := analysis.classes_by_neat_id.get(class_neat_id):
            if property_link_pairs:
                property_renaming_config = {
                    prop_uri: prop_name
                    for prop_name, prop_neat_id in property_link_pairs.items()
                    if (prop_uri := analysis.neat_id_to_instance_source_property_uri(prop_neat_id))
                }
                if information_properties := analysis.classes_with_properties(consider_inheritance=True).get(
                    cls.class_
                ):
                    for prop in information_properties:
                        if prop.neatId is None:
                            continue
                        # Include renaming done in the Information rules that are not present in the
                        # property_link_pairs. The use case for this renaming to startNode and endNode
                        # properties that are not part of DMSRules but will typically be present
                        # in the Information rules.
                        if (
                            uri := analysis.neat_id_to_instance_source_property_uri(prop.neatId)
                        ) and uri not in property_renaming_config:
                            property_renaming_config[uri] = prop.property_

                yield from self._read_via_class_entity(cls.class_, property_renaming_config)
                return
            else:
                warnings.warn("Rules not linked", stacklevel=2)
                return
        else:
            warnings.warn("Class with neat id {class_neat_id} found in rules", stacklevel=2)
            return

    def _read_via_class_entity(
        self,
        class_entity: ClassEntity,
        property_renaming_config: dict[URIRef, str] | None = None,
        named_graph: URIRef | None = None,
    ) -> Iterable[tuple[str, dict[str | InstanceType, list[str]]]]:
        named_graph = named_graph or self.default_named_graph

        if named_graph not in self.named_graphs:
            warnings.warn(
                f"Named graph {named_graph} not found in graph store, cannot read",
                stacklevel=2,
            )
            return

        if not self.rules or named_graph not in self.rules:
            warnings.warn(
                f"Rules for named graph {named_graph} not found in graph store!",
                stacklevel=2,
            )
            return
        if self.multi_type_instances:
            warnings.warn(
                "Multi typed instances detected, issues with loading can occur!",
                stacklevel=2,
            )

        if class_entity not in [definition.class_ for definition in self.rules[named_graph].classes]:
            warnings.warn("Desired type not found in graph!", stacklevel=2)
            return

        if not (class_uri := InformationAnalysis(self.rules[named_graph]).class_uri(class_entity)):
            warnings.warn(
                f"Class {class_entity.suffix} does not have namespace defined for prefix {class_entity.prefix} Rules!",
                stacklevel=2,
            )
            return

        has_hop_transformations = InformationAnalysis(self.rules[named_graph]).has_hop_transformations()
        has_self_reference_transformations = InformationAnalysis(
            self.rules[named_graph]
        ).has_self_reference_property_transformations()
        if has_hop_transformations or has_self_reference_transformations:
            msg = (
                f"Rules contain [{'Hop' if has_hop_transformations else ''}"
                f", {'SelfReferenceProperty' if has_self_reference_transformations else ''}]"
                " rdfpath."
                f" Run [{'ReduceHopTraversal' if has_hop_transformations else ''}"
                f", {'AddSelfReferenceProperty' if has_self_reference_transformations else ''}]"
                " transformer(s) first!"
            )

            warnings.warn(
                msg,
                stacklevel=2,
            )
            return

        # get all the instances for give class_uri
        instance_ids = self.queries.list_instances_ids_of_class(class_uri)

        # get potential property renaming config
        property_renaming_config = property_renaming_config or InformationAnalysis(
            self.rules[named_graph]
        ).define_property_renaming_config(class_entity)

        for instance_id in instance_ids:
            if res := self.queries.describe(
                instance_id=instance_id,
                instance_type=class_entity.suffix,
                property_renaming_config=property_renaming_config,
            ):
                yield res

    def read(
        self, class_: str, named_graph: URIRef | None = None
    ) -> Iterable[tuple[str, dict[str | InstanceType, list[str]]]]:
        """Read instances for given class from the graph store.

        !!! note "Assumption"
            This method assumes that the class_ belongs to the same (name)space as
            the rules which are attached to the graph store.

        """
        named_graph = named_graph or self.default_named_graph

        if named_graph not in self.named_graphs:
            warnings.warn(
                f"Named graph {named_graph} not found in graph store, cannot read",
                stacklevel=2,
            )
            return

        if not self.rules or named_graph not in self.rules:
            warnings.warn(
                f"Rules for named graph {named_graph} not found in graph store!",
                stacklevel=2,
            )
            return
        if self.multi_type_instances:
            warnings.warn(
                "Multi typed instances detected, issues with loading can occur!",
                stacklevel=2,
            )

        class_entity = ClassEntity(prefix=self.rules[named_graph].metadata.prefix, suffix=class_)

        if class_entity not in [definition.class_ for definition in self.rules[named_graph].classes]:
            warnings.warn("Desired type not found in graph!", stacklevel=2)
            return

        yield from self._read_via_class_entity(class_entity)

    def count_of_id(self, neat_id: URIRef, named_graph: URIRef | None = None) -> int:
        """Count the number of instances of a given type

        Args:
            neat_id: Type for which instances are to be counted

        Returns:
            Number of instances
        """
        named_graph = named_graph or self.default_named_graph

        if named_graph not in self.named_graphs:
            warnings.warn(
                f"Named graph {named_graph} not found in graph store, cannot count",
                stacklevel=2,
            )
            return 0

        if not self.rules or named_graph not in self.rules:
            warnings.warn(
                f"Rules for named graph {named_graph} not found in graph store!",
                stacklevel=2,
            )
            return 0

        class_entity = next(
            (definition.class_ for definition in self.rules[named_graph].classes if definition.neatId == neat_id),
            None,
        )
        if not class_entity:
            warnings.warn("Desired type not found in graph!", stacklevel=2)
            return 0

        if not (class_uri := InformationAnalysis(self.rules[named_graph]).class_uri(class_entity)):
            warnings.warn(
                f"Class {class_entity.suffix} does not have namespace defined for prefix {class_entity.prefix} Rules!",
                stacklevel=2,
            )
            return 0

        return self.count_of_type(class_uri)

    def count_of_type(self, class_uri: URIRef) -> int:
        query = f"SELECT (COUNT(?instance) AS ?instanceCount) WHERE {{ ?instance a <{class_uri}> }}"
        return int(next(iter(self.dataset.query(query)))[0])  # type: ignore[arg-type, index]

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

    def transform(self, transformer: Transformers, named_graph: URIRef | None = None) -> None:
        """Transforms the graph store using a transformer."""

        named_graph = named_graph or self.default_named_graph
        if named_graph in self.named_graphs:
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
                transformer.transform(self.graph(named_graph))
                self.provenance.append(
                    Change.record(
                        activity=f"{type(transformer).__name__}",
                        start=_start,
                        end=datetime.now(timezone.utc),
                        description=transformer.description,
                    )
                )

        else:
            warnings.warn(
                f"Named graph {named_graph} not found in graph store, cannot transform",
                stacklevel=2,
            )

    @property
    def summary(self) -> dict[URIRef, pd.DataFrame]:
        return {
            named_graph: pd.DataFrame(
                self.queries.summarize_instances(named_graph),
                columns=["Type", "Occurrence"],
            )
            for named_graph in self.named_graphs
        }

    @property
    def multi_type_instances(self) -> dict[URIRef, dict[str, list[str]]]:
        return {named_graph: self.queries.multi_type_instances(named_graph) for named_graph in self.named_graphs}

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
        return not self.queries.has_data()
