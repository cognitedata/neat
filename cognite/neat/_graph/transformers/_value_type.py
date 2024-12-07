import warnings
from collections.abc import Callable
from typing import Any

import rdflib
from rdflib import RDF, XSD, Graph, Namespace, URIRef

from cognite.neat._constants import UNKNOWN_TYPE
from cognite.neat._graph.queries import Queries
from cognite.neat._issues.warnings import PropertyDataTypeConversionWarning
from cognite.neat._utils.collection_ import iterate_progress_bar
from cognite.neat._utils.rdf_ import get_namespace, remove_namespace_from_uri

from ._base import BaseTransformer


class SplitMultiValueProperty(BaseTransformer):
    description: str = (
        "SplitMultiValueProperty is a transformer that splits a "
        "multi-value property into multiple single-value properties."
    )
    _use_only_once: bool = True
    _need_changes = frozenset({})

    _object_property_template: str = """SELECT ?s ?o WHERE{{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                ?o a <{object_uri}> .

                            }}"""

    _datatype_property_template: str = """SELECT ?s ?o WHERE {{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                FILTER (datatype(?o) = <{object_uri}>)

                                }}"""

    _unknown_property_template: str = """SELECT ?s ?o WHERE {{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                FILTER NOT EXISTS {{ ?o a ?objectType }}
                                }}"""

    def transform(self, graph: Graph) -> None:
        # handle multi value type object properties
        for subject_uri, property_uri, value_types in Queries(graph).multi_value_type_property():
            for value_type_uri in value_types:
                _args = {
                    "subject_uri": subject_uri,
                    "property_uri": property_uri,
                    "object_uri": value_type_uri,
                }

                # Case 1: Unknown value type
                if value_type_uri == UNKNOWN_TYPE:
                    iterator = graph.query(self._unknown_property_template.format(**_args))

                # Case 2: Datatype value type
                elif value_type_uri.startswith(str(XSD)):
                    iterator = graph.query(self._datatype_property_template.format(**_args))

                # Case 3: Object value type
                else:
                    iterator = graph.query(self._object_property_template.format(**_args))

                for s, o in iterator:  # type: ignore [misc]
                    graph.remove((s, property_uri, o))
                    new_property = URIRef(f"{property_uri}_{remove_namespace_from_uri(value_type_uri)}")
                    graph.add((s, new_property, o))


class ConvertLiteral(BaseTransformer):
    description: str = "ConvertLiteral is a transformer that converts a literal value."
    _use_only_once: bool = False
    _need_changes = frozenset({})

    _count_by_properties = """SELECT (COUNT(?property) AS ?propertyCount)
    WHERE {{
      ?instance a <{subject_type}> .
      ?instance <{subject_predicate}> ?property
    }}"""

    _properties = """SELECT ?instance ?property
    WHERE {{
      ?instance a <{subject_type}> .
      ?instance <{subject_predicate}> ?property
    }}"""

    def __init__(
        self,
        subject_type: URIRef,
        subject_predicate: URIRef,
        conversion: Callable[[Any], Any],
    ) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.conversion = conversion
        self._type_name = remove_namespace_from_uri(subject_type)
        self._property_name = remove_namespace_from_uri(subject_predicate)

    def transform(self, graph: Graph) -> None:
        count_query = self._count_by_properties.format(
            subject_type=self.subject_type, subject_predicate=self.subject_predicate
        )

        property_count_res = list(graph.query(count_query))
        property_count = int(property_count_res[0][0])  # type: ignore [index, arg-type]
        iterate_query = self._properties.format(
            subject_type=self.subject_type, subject_predicate=self.subject_predicate
        )

        for instance, literal in iterate_progress_bar(  # type: ignore[misc]
            graph.query(iterate_query),
            total=property_count,
            description=f"Converting {self._type_name}.{self._property_name}.",
        ):
            if not isinstance(literal, rdflib.Literal):
                warnings.warn(
                    PropertyDataTypeConversionWarning(
                        str(instance),
                        self._type_name,
                        self._property_name,
                        "The value is a connection and not a data type.",
                    ),
                    stacklevel=2,
                )
                continue
            value = literal.toPython()
            try:
                converted_value = self.conversion(value)
            except Exception as e:
                warnings.warn(
                    PropertyDataTypeConversionWarning(str(instance), self._type_name, self._property_name, str(e)),
                    stacklevel=2,
                )
                continue

            graph.add((instance, self.subject_predicate, rdflib.Literal(converted_value)))
            graph.remove((instance, self.subject_predicate, literal))


class LiteralToEntity(BaseTransformer):
    description = "Converts a literal value to new entity"

    _count_properties_of_type = """SELECT (COUNT(?property) AS ?propertyCount)
    WHERE {{
      ?instance a <{subject_type}> .
      ?instance <{subject_predicate}> ?property
    }}"""

    _properties_of_type = """SELECT ?instance ?property
    WHERE {{
      ?instance a <{subject_type}> .
      ?instance <{subject_predicate}> ?property
    }}"""

    _count_properties = """SELECT (COUNT(?property) AS ?propertyCount)
    WHERE {{
      ?instance <{subject_predicate}> ?property
    }}"""

    _properties = """SELECT ?instance ?property
    WHERE {{
      ?instance <{subject_predicate}> ?property
    }}"""

    def __init__(
        self, subject_type: URIRef | None, subject_predicate: URIRef, entity_type: str, new_property: str | None = None
    ) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.entity_type = entity_type
        self.new_property = new_property

    def transform(self, graph: Graph) -> None:
        if self.subject_type is None:
            count_query = self._count_properties.format(subject_predicate=self.subject_predicate)
            iterate_query = self._properties.format(subject_predicate=self.subject_predicate)
        else:
            count_query = self._count_properties_of_type.format(
                subject_type=self.subject_type, subject_predicate=self.subject_predicate
            )
            iterate_query = self._properties_of_type.format(
                subject_type=self.subject_type, subject_predicate=self.subject_predicate
            )

        property_count_res = list(graph.query(count_query))
        property_count = int(property_count_res[0][0])  # type: ignore [index, arg-type]

        instance: URIRef
        for instance, literal in iterate_progress_bar(  # type: ignore[misc, assignment]
            graph.query(iterate_query),
            total=property_count,
            description=f"Converting {remove_namespace_from_uri(self.subject_predicate)}.",
        ):
            if not isinstance(literal, rdflib.Literal):
                warnings.warn(
                    PropertyDataTypeConversionWarning(
                        str(instance),
                        remove_namespace_from_uri(self.subject_type) if self.subject_type else "Unknown",
                        remove_namespace_from_uri(self.subject_predicate),
                        "The value is a connection and not a data type.",
                    ),
                    stacklevel=2,
                )
                continue
            namespace = Namespace(get_namespace(instance))
            value = literal.toPython()
            entity_type = namespace[self.entity_type]
            new_entity = namespace[f"{self.entity_type}_{value!s}"]
            graph.add((new_entity, RDF.type, entity_type))
            if self.new_property is not None:
                graph.add((instance, namespace[self.new_property], rdflib.Literal(value)))
            graph.add((instance, self.subject_predicate, new_entity))
            graph.remove((instance, self.subject_predicate, literal))
