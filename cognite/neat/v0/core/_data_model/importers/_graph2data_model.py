import itertools
import urllib.parse
import warnings
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from rdflib import RDF, RDFS, Namespace, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.query import ResultRow

from cognite.neat.v0.core._config import GLOBAL_CONFIG
from cognite.neat.v0.core._constants import NEAT
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.models import UnverifiedConceptualDataModel
from cognite.neat.v0.core._data_model.models._import_contexts import GraphContext
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.entities import UnknownEntity
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.warnings import NeatValueWarning
from cognite.neat.v0.core._store import NeatInstanceStore
from cognite.neat.v0.core._utils.collection_ import iterate_progress_bar
from cognite.neat.v0.core._utils.rdf_ import split_uri

from ._base import BaseImporter


# Internal helper class
@dataclass
class _ReadProperties:
    type_uri: URIRef
    property_uri: URIRef
    value_type: URIRef
    parent_uri: URIRef | None
    max_occurrence: int
    instance_count: int


class GraphImporter(BaseImporter[UnverifiedConceptualDataModel]):
    """Infers a data model from the triples in a Graph Store.
    Args:
        store: The graph store to read from.
        data_model_id: The data model id to be used for the imported rules.
    """

    _ORDERED_CONCEPTS_QUERY = """SELECT DISTINCT ?concept (count(?s) as ?instances )
                           WHERE { ?s a ?concept }
                           group by ?concept order by DESC(?instances)"""

    _TYPE_PARENT_QUERY = f"""SELECT ?parent ?type
                            WHERE {{ ?s a ?type .
                            ?type <{RDFS.subClassOf}> ?parent }}"""

    _PROPERTIES_QUERY = """SELECT DISTINCT ?property ?valueType
                         WHERE {{
                            ?s a <{type}> .
                            ?s ?property ?object .
                            OPTIONAL {{ ?object a ?objectType }}
                            BIND(
                               IF(
                                    isLiteral(?object), datatype(?object),
                                    IF(BOUND(?objectType), ?objectType, <{unknown_type}>)
                                ) AS ?valueType
                            )
                        }}"""

    _MAX_OCCURRENCE_QUERY = """SELECT (MAX(?count) AS ?maxCount)
                            WHERE {{
                              {{
                                SELECT ?subject (COUNT(?object) AS ?count)
                                WHERE {{
                                  ?subject a <{type}> .
                                  ?subject <{property}> ?object .
                                }}
                                GROUP BY ?subject
                              }}
                            }}"""

    def __init__(
        self,
        store: NeatInstanceStore,
        data_model_id: DataModelIdentifier = ("neat_space", "NeatInferredDataModel", "v1"),
    ) -> None:
        self.store = store
        self.data_model_id = DataModelId.load(data_model_id)
        if self.data_model_id.version is None:
            raise NeatValueError("Version is required when setting a Data Model ID")

    def to_data_model(self) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        metadata = self._create_default_metadata()
        if not self.store.queries.select.has_data():
            warnings.warn(NeatValueWarning("Cannot infer data model. No data found in the graph."), stacklevel=2)
            return ImportedDataModel(UnverifiedConceptualDataModel(metadata, [], [], {}), None)

        parent_by_child = self._read_parent_by_child_from_graph()
        count_by_type = self._read_types_with_counts_from_graph()
        if not count_by_type:
            warnings.warn(
                NeatValueWarning("Cannot infer data model. No RDF.type triples found in the graph."), stacklevel=2
            )
            return ImportedDataModel(UnverifiedConceptualDataModel(metadata, [], [], {}), None)

        read_properties = self._read_concept_properties_from_graph(count_by_type, parent_by_child)

        prefixes: dict[str, Namespace] = {}
        concepts, properties = self._create_concepts_properties(read_properties, prefixes)

        return ImportedDataModel(
            UnverifiedConceptualDataModel(
                metadata=metadata,
                concepts=concepts,
                properties=properties,
                prefixes=prefixes,
            ),
            context=GraphContext({"inferred_from": count_by_type}),
        )

    def _read_parent_by_child_from_graph(self) -> dict[URIRef, URIRef]:
        parent_by_child: dict[URIRef, URIRef] = {}
        for result_row in self.store.dataset.query(self._TYPE_PARENT_QUERY):
            parent_uri, child_uri = cast(tuple[URIRef, URIRef], result_row)
            parent_by_child[child_uri] = parent_uri
        return parent_by_child

    def _read_types_with_counts_from_graph(self) -> dict[URIRef, int]:
        count_by_type: dict[URIRef, int] = {}
        # Reads all types and their instance counts from the graph
        for result_row in self.store.dataset.query(self._ORDERED_CONCEPTS_QUERY):
            type_uri, instance_count_literal = cast(tuple[URIRef, RdfLiteral], result_row)
            count_by_type[type_uri] = instance_count_literal.toPython()
        return count_by_type

    def _read_concept_properties_from_graph(
        self, count_by_type: dict[URIRef, int], parent_by_child: dict[URIRef, URIRef]
    ) -> list[_ReadProperties]:
        read_properties: list[_ReadProperties] = []

        total_instance_count = sum(count_by_type.values())
        iterable = count_by_type.items()
        if GLOBAL_CONFIG.use_iterate_bar_threshold and total_instance_count > GLOBAL_CONFIG.use_iterate_bar_threshold:
            iterable = iterate_progress_bar(iterable, len(count_by_type), "Inferring types...")  # type: ignore[assignment]

        for type_uri, instance_count in iterable:
            property_query = self._PROPERTIES_QUERY.format(type=type_uri, unknown_type=NEAT.UnknownType)
            for result_row in self.store.dataset.query(property_query):
                property_uri, value_type_uri = cast(tuple[URIRef, URIRef], result_row)
                if property_uri == RDF.type:
                    continue
                occurrence_query = self._MAX_OCCURRENCE_QUERY.format(type=type_uri, property=property_uri)
                max_occurrence = 1  # default value
                # We know that the _MAX_OCCURRENCE_QUERY will return a ResultRow
                occurrence_results = list(cast(ResultRow, self.store.dataset.query(occurrence_query)))
                if occurrence_results and occurrence_results[0] and occurrence_results[0][0]:
                    max_occurrence_literal = cast(RdfLiteral, occurrence_results[0][0])
                    max_occurrence = int(max_occurrence_literal.toPython())
                read_properties.append(
                    _ReadProperties(
                        type_uri=type_uri,
                        property_uri=property_uri,
                        parent_uri=parent_by_child.get(type_uri),
                        value_type=value_type_uri,
                        max_occurrence=max_occurrence,
                        instance_count=instance_count,
                    )
                )
        return read_properties

    def _create_concepts_properties(
        self, read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]
    ) -> tuple[list[UnverifiedConcept], list[UnverifiedConceptualProperty]]:
        concepts: list[UnverifiedConcept] = []
        properties: list[UnverifiedConceptualProperty] = []

        # Help for IDE
        type_uri: URIRef
        parent_uri: URIRef
        for parent_uri, parent_concepts_properties_iterable in itertools.groupby(
            sorted(read_properties, key=lambda x: x.parent_uri or NEAT.EmptyType),
            key=lambda x: x.parent_uri or NEAT.EmptyType,
        ):
            parent_str: str | None = None
            if parent_uri != NEAT.EmptyType:
                parent_str, parent_cls = self._create_concept(parent_uri, set_instance_source=False, prefixes=prefixes)
                concepts.append(parent_cls)

            properties_by_concept_by_property = self._get_properties_by_concept_by_property(
                parent_concepts_properties_iterable
            )
            for type_uri, properties_by_property_uri in properties_by_concept_by_property.items():
                concept_str, concept = self._create_concept(
                    type_uri, set_instance_source=True, prefixes=prefixes, implements=parent_str
                )
                concepts.append(concept)
                for property_uri, read_properties in properties_by_property_uri.items():
                    namespace, property_suffix = split_uri(property_uri)
                    (self._add_uri_namespace_to_prefixes(namespace, prefixes),)
                    properties.append(
                        self._create_property(
                            read_properties, concept_str, property_uri, urllib.parse.unquote(property_suffix), prefixes
                        )
                    )
        return concepts, properties

    @staticmethod
    def _get_properties_by_concept_by_property(
        parent_concept_properties_iterable: Iterable[_ReadProperties],
    ) -> dict[URIRef, dict[URIRef, list[_ReadProperties]]]:
        properties_by_concept_by_property: dict[URIRef, dict[URIRef, list[_ReadProperties]]] = {}
        for concept_uri, concept_properties_iterable in itertools.groupby(
            sorted(parent_concept_properties_iterable, key=lambda x: x.type_uri), key=lambda x: x.type_uri
        ):
            properties_by_concept_by_property[concept_uri] = defaultdict(list)
            for read_prop in concept_properties_iterable:
                properties_by_concept_by_property[concept_uri][read_prop.property_uri].append(read_prop)
        return properties_by_concept_by_property

    @classmethod
    def _create_concept(
        cls, type_uri: URIRef, set_instance_source: bool, prefixes: dict[str, Namespace], implements: str | None = None
    ) -> tuple[str, UnverifiedConcept]:
        namespace, suffix = split_uri(type_uri)
        cls._add_uri_namespace_to_prefixes(namespace, prefixes)
        concept_str = urllib.parse.unquote(suffix)
        return concept_str, UnverifiedConcept(
            concept=concept_str, implements=implements, instance_source=type_uri if set_instance_source else None
        )

    def _create_property(
        self,
        read_properties: list[_ReadProperties],
        concept_str: str,
        property_uri: URIRef,
        property_id: str,
        prefixes: dict[str, Namespace],
    ) -> UnverifiedConceptualProperty:
        first = read_properties[0]
        value_type = self._get_value_type(read_properties, prefixes)
        return UnverifiedConceptualProperty(
            concept=concept_str,
            property_=property_id,
            max_count=first.max_occurrence,
            value_type=value_type,
            instance_source=[property_uri],
        )

    @classmethod
    def _get_value_type(
        cls, read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]
    ) -> str | UnknownEntity:
        value_types = {prop.value_type for prop in read_properties}
        if len(value_types) == 1:
            uri_ref = value_types.pop()
            if uri_ref == NEAT.UnknownType:
                return UnknownEntity()
            namespace, suffix = split_uri(uri_ref)
            cls._add_uri_namespace_to_prefixes(namespace, prefixes)
            return suffix
        uri_refs: list[str] = []
        for uri_ref in value_types:
            if uri_ref == NEAT.UnknownType:
                return UnknownEntity()
            namespace, suffix = split_uri(uri_ref)
            cls._add_uri_namespace_to_prefixes(namespace, prefixes)
            uri_refs.append(suffix)
        # Sort the URIs to ensure deterministic output
        return ", ".join(sorted(uri_refs))

    def _create_default_metadata(self) -> UnverifiedConceptualMetadata:
        now = datetime.now(timezone.utc)
        name = self.data_model_id.external_id.replace("_", " ").title()
        return UnverifiedConceptualMetadata(
            space=self.data_model_id.space,
            external_id=self.data_model_id.external_id,
            # Validated in the constructor
            version=cast(str, self.data_model_id.version),
            name=name,
            creator="NEAT",
            created=now,
            updated=now,
            description="Inferred model from knowledge graph",
        )

    @classmethod
    def _add_uri_namespace_to_prefixes(cls, namespace: str, prefixes: dict[str, Namespace]) -> None:
        """Add URI to prefixes dict if not already present

        Args:
            URI: URI from which namespace is being extracted
            prefixes: Dict of prefixes and namespaces
        """
        if Namespace(namespace) not in prefixes.values():
            prefixes[f"prefix_{len(prefixes) + 1}"] = Namespace(namespace)
