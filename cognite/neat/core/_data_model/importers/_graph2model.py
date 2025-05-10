import itertools
import urllib.parse
import warnings
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from rdflib import RDF, RDFS, Namespace, URIRef
from rdflib import Literal as RdfLiteral

from cognite.neat.core._config import GLOBAL_CONFIG
from cognite.neat.core._constants import NEAT
from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.models import InformationInputRules
from cognite.neat.core._data_model.models.entities import UnknownEntity
from cognite.neat.core._data_model.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._store import NeatGraphStore
from cognite.neat.core._utils.collection_ import iterate_progress_bar
from cognite.neat.core._utils.rdf_ import split_uri

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


class GraphImporter(BaseImporter[InformationInputRules]):
    """Infers a data model from the triples in a Graph Store.

    Args:
        store: The graph store to read from.
        data_model_id: The data model id to be used for the imported rules.

    """

    _ordered_class_query = """SELECT DISTINCT ?class (count(?s) as ?instances )
                           WHERE { ?s a ?class }
                           group by ?class order by DESC(?instances)"""

    _type_parent_query = f"""SELECT ?parent ?type
                            WHERE {{ ?s a ?type .
                            ?type <{RDFS.subClassOf}> ?parent }}"""

    _properties_query = """SELECT DISTINCT ?property ?valueType
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

    _max_occurrence_query = """SELECT (MAX(?count) AS ?maxCount)
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
        store: NeatGraphStore,
        data_model_id: DataModelIdentifier = ("neat_space", "NeatInferredDataModel", "v1"),
    ) -> None:
        self.store = store
        self.data_model_id = DataModelId.load(data_model_id)
        if self.data_model_id.version is None:
            raise NeatValueError("Version is required when setting a Data Model ID")

    def to_rules(self) -> ReadRules[InformationInputRules]:
        metadata = self._create_default_metadata()
        if not self.store.queries.select.has_data():
            warnings.warn(NeatValueWarning("Cannot infer data model. No data found in the graph."), stacklevel=2)
            return ReadRules(InformationInputRules(metadata, [], [], {}), {})

        parent_by_child = self._read_parent_by_child_from_graph()
        count_by_type = self._read_types_with_counts_from_graph()
        if not count_by_type:
            warnings.warn(
                NeatValueWarning("Cannot infer data model. No RDF.type triples found in the graph."), stacklevel=2
            )
            return ReadRules(InformationInputRules(metadata, [], [], {}), {})

        read_properties = self._read_class_properties_from_graph(count_by_type, parent_by_child)

        prefixes: dict[str, Namespace] = {}
        classes, properties = self._create_classes_properties(read_properties, prefixes)
        read_context: dict[str, object] = {"inferred_from": count_by_type}

        return ReadRules(
            InformationInputRules(
                metadata=metadata,
                classes=classes,
                properties=properties,
                prefixes=prefixes,
            ),
            read_context=read_context,
        )

    def _read_parent_by_child_from_graph(self) -> dict[URIRef, URIRef]:
        parent_by_child: dict[URIRef, URIRef] = {}
        for result_row in self.store.dataset.query(self._type_parent_query):
            parent_uri, child_uri = cast(tuple[URIRef, URIRef], result_row)
            parent_by_child[child_uri] = parent_uri
        return parent_by_child

    def _read_types_with_counts_from_graph(self) -> dict[URIRef, int]:
        count_by_type: dict[URIRef, int] = {}
        # Reads all types and their instance counts from the graph
        for result_row in self.store.dataset.query(self._ordered_class_query):
            type_uri, instance_count_literal = cast(tuple[URIRef, RdfLiteral], result_row)
            count_by_type[type_uri] = instance_count_literal.toPython()
        return count_by_type

    def _read_class_properties_from_graph(
        self, count_by_type: dict[URIRef, int], parent_by_child: dict[URIRef, URIRef]
    ) -> list[_ReadProperties]:
        read_properties: list[_ReadProperties] = []

        total_instance_count = sum(count_by_type.values())
        iterable = count_by_type.items()
        if GLOBAL_CONFIG.use_iterate_bar_threshold and total_instance_count > GLOBAL_CONFIG.use_iterate_bar_threshold:
            iterable = iterate_progress_bar(iterable, len(count_by_type), "Inferring types...")  # type: ignore[assignment]

        for type_uri, instance_count in iterable:
            property_query = self._properties_query.format(type=type_uri, unknown_type=NEAT.UnknownType)
            for result_row in self.store.dataset.query(property_query):
                property_uri, value_type_uri = cast(tuple[URIRef, URIRef], result_row)
                if property_uri == RDF.type:
                    continue
                occurrence_query = self._max_occurrence_query.format(type=type_uri, property=property_uri)
                max_occurrence = 1  # default value
                occurrence_row, *_ = list(self.store.dataset.query(occurrence_query))
                if occurrence_row:
                    max_occurrence_literal, *__ = cast(tuple[RdfLiteral, Any], occurrence_row)
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

    def _create_classes_properties(
        self, read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]
    ) -> tuple[list[InformationInputClass], list[InformationInputProperty]]:
        classes: list[InformationInputClass] = []
        properties: list[InformationInputProperty] = []

        # Help for IDE
        type_uri: URIRef
        parent_uri: URIRef
        for parent_uri, parent_class_properties_iterable in itertools.groupby(
            sorted(read_properties, key=lambda x: x.parent_uri or NEAT.EmptyType),
            key=lambda x: x.parent_uri or NEAT.EmptyType,
        ):
            parent_str: str | None = None
            if parent_uri != NEAT.EmptyType:
                parent_str, parent_cls = self._create_class(parent_uri, set_instance_source=False, prefixes=prefixes)
                classes.append(parent_cls)

            properties_by_class_by_property = self._get_properties_by_class_by_property(
                parent_class_properties_iterable
            )
            for type_uri, properties_by_property_uri in properties_by_class_by_property.items():
                class_str, class_ = self._create_class(
                    type_uri, set_instance_source=True, prefixes=prefixes, implements=parent_str
                )
                classes.append(class_)
                for property_uri, read_properties in properties_by_property_uri.items():
                    namespace, property_suffix = split_uri(property_uri)
                    if namespace not in prefixes:
                        prefixes[namespace] = Namespace(namespace)
                    properties.append(
                        self._create_property(
                            read_properties, class_str, property_uri, urllib.parse.unquote(property_suffix), prefixes
                        )
                    )
        return classes, properties

    @staticmethod
    def _get_properties_by_class_by_property(
        parent_class_properties_iterable: Iterable[_ReadProperties],
    ) -> dict[URIRef, dict[URIRef, list[_ReadProperties]]]:
        properties_by_class_by_property: dict[URIRef, dict[URIRef, list[_ReadProperties]]] = {}
        for class_uri, class_properties_iterable in itertools.groupby(
            sorted(parent_class_properties_iterable, key=lambda x: x.type_uri), key=lambda x: x.type_uri
        ):
            properties_by_class_by_property[class_uri] = defaultdict(list)
            for read_prop in class_properties_iterable:
                properties_by_class_by_property[class_uri][read_prop.property_uri].append(read_prop)
        return properties_by_class_by_property

    @staticmethod
    def _create_class(
        type_uri: URIRef, set_instance_source: bool, prefixes: dict[str, Namespace], implements: str | None = None
    ) -> tuple[str, InformationInputClass]:
        namespace, suffix = split_uri(type_uri)
        if namespace not in prefixes:
            prefixes[namespace] = Namespace(namespace)
        class_str = urllib.parse.unquote(suffix)
        return class_str, InformationInputClass(
            class_=class_str, implements=implements, instance_source=type_uri if set_instance_source else None
        )

    def _create_property(
        self,
        read_properties: list[_ReadProperties],
        class_str: str,
        property_uri: URIRef,
        property_id: str,
        prefixes: dict[str, Namespace],
    ) -> InformationInputProperty:
        first = read_properties[0]
        value_type = self._get_value_type(read_properties, prefixes)
        return InformationInputProperty(
            class_=class_str,
            property_=property_id,
            max_count=first.max_occurrence,
            value_type=value_type,
            instance_source=[property_uri],
        )

    @staticmethod
    def _get_value_type(read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]) -> str | UnknownEntity:
        value_types = {prop.value_type for prop in read_properties}
        if len(value_types) == 1:
            uri_ref = value_types.pop()
            if uri_ref == NEAT.UnknownType:
                return UnknownEntity()
            namespace, suffix = split_uri(uri_ref)
            if namespace not in prefixes:
                prefixes[namespace] = Namespace(namespace)
            return suffix
        elif len(value_types) == 0:
            return UnknownEntity()
        uri_refs: list[str] = []
        for uri_ref in value_types:
            if uri_ref == NEAT.UnknownType:
                return UnknownEntity()
            namespace, suffix = split_uri(uri_ref)
            if namespace not in prefixes:
                prefixes[namespace] = Namespace(namespace)
            uri_refs.append(suffix)
        # Sort the URIs to ensure deterministic output
        return ", ".join(sorted(uri_refs))

    def _create_default_metadata(self) -> InformationInputMetadata:
        now = datetime.now(timezone.utc)
        name = self.data_model_id.external_id.replace("_", " ").title()
        return InformationInputMetadata(
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
