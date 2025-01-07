import warnings
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import quote

import rdflib
from rdflib import RDF, XSD, Graph, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat._constants import UNKNOWN_TYPE
from cognite.neat._graph.queries import Queries
from cognite.neat._issues.warnings import PropertyDataTypeConversionWarning
from cognite.neat._utils.auxiliary import string_to_ideal_type
from cognite.neat._utils.rdf_ import get_namespace, remove_namespace_from_uri

from ._base import BaseTransformer, BaseTransformerStandardised, RowTransformationOutput


# TODO: Standardise
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


class ConvertLiteral(BaseTransformerStandardised):
    description: str = "ConvertLiteral is a transformer that improve data typing of a literal value."
    _use_only_once: bool = False
    _need_changes = frozenset({})

    def __init__(
        self,
        subject_type: URIRef,
        subject_predicate: URIRef,
        conversion: Callable[[Any], Any] | None = None,
    ) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.conversion = conversion or string_to_ideal_type
        self._type_name = remove_namespace_from_uri(subject_type)
        self._property_name = remove_namespace_from_uri(subject_predicate)

    def _skip_count_query(self) -> str:
        query = """SELECT (COUNT(?value) AS ?valueCount)
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?value
                       FILTER(isIRI(?value))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _count_query(self) -> str:
        query = """SELECT (COUNT(?value) AS ?valueCount)
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?value
                       FILTER(isLiteral(?value))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _iterate_query(self) -> str:
        query = """SELECT ?instance ?value
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?value
                      FILTER(isLiteral(?value))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        instance, literal = query_result_row
        value = cast(rdflib.Literal, literal).toPython()

        try:
            converted_value = self.conversion(value)
        except Exception as e:
            warnings.warn(
                PropertyDataTypeConversionWarning(str(instance), self._type_name, self._property_name, str(e)),
                stacklevel=2,
            )
        row_output.add_triples.append((instance, self.subject_predicate, rdflib.Literal(converted_value)))  # type: ignore[arg-type]
        row_output.remove_triples.append((instance, self.subject_predicate, literal))  # type: ignore[arg-type]
        row_output.instances_modified_count += 1

        return row_output


class LiteralToEntity(BaseTransformerStandardised):
    description = "Converts a literal value to new entity"

    def __init__(
        self, subject_type: URIRef | None, subject_predicate: URIRef, entity_type: str, new_property: str | None = None
    ) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.entity_type = entity_type
        self.new_property = new_property

    def _iterate_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT ?instance ?property
            WHERE {{
              ?instance <{subject_predicate}> ?property
              FILTER(isLiteral(?property))
            }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT ?instance ?property
                WHERE {{
                  ?instance a <{subject_type}> .
                  ?instance <{subject_predicate}> ?property
                  FILTER(isLiteral(?property))
                }}"""
            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _skip_count_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT (COUNT(?property) AS ?propertyCount)
                        WHERE {{
                          ?instance <{subject_predicate}> ?property
                          FILTER(isIRI(?property))
                        }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT (COUNT(?property) AS ?propertyCount)
                        WHERE {{
                          ?instance a <{subject_type}> .
                          ?instance <{subject_predicate}> ?property
                          FILTER(isIRI(?property))
                        }}"""
            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _count_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT (COUNT(?property) AS ?propertyCount)
                WHERE {{
                  ?instance <{subject_predicate}> ?property
                  FILTER(isLiteral(?property))
                }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT (COUNT(?property) AS ?propertyCount)
                        WHERE {{
                          ?instance a <{subject_type}> .
                          ?instance <{subject_predicate}> ?property
                          FILTER(isLiteral(?property))
                        }}"""

            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        instance, literal = query_result_row
        value = cast(rdflib.Literal, literal).toPython()
        namespace = Namespace(get_namespace(instance))  # type: ignore[arg-type]
        entity_type = namespace[self.entity_type]
        new_entity = namespace[f"{self.entity_type}_{quote(value)!s}"]
        row_output.add_triples.append((new_entity, RDF.type, entity_type))
        row_output.instances_added_count += 1  # we add one new entity

        if self.new_property is not None:
            row_output.add_triples.append((new_entity, namespace[self.new_property], rdflib.Literal(value)))  # type: ignore[arg-type]
            row_output.instances_modified_count += 1  # we modify the new entity

        row_output.add_triples.append((instance, self.subject_predicate, new_entity))  # type: ignore[arg-type]
        row_output.remove_triples.append((instance, self.subject_predicate, literal))  # type: ignore[arg-type]
        row_output.instances_modified_count += 1  # we modify the old entity

        return row_output


class ConnectionToLiteral(BaseTransformerStandardised):
    description = "Converts an entity connection to a literal value"

    def __init__(self, subject_type: URIRef | None, subject_predicate: URIRef) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate

    def _iterate_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT ?instance ?object
            WHERE {{
              ?instance <{subject_predicate}> ?object
              FILTER(isIRI(?object))
            }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT ?instance ?object
                WHERE {{
                  ?instance a <{subject_type}> .
                  ?instance <{subject_predicate}> ?object
                  FILTER(isIRI(?object))
                }}"""
            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _skip_count_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT (COUNT(?object) AS ?objectCount)
                        WHERE {{
                          ?instance <{subject_predicate}> ?object
                          FILTER(isLiteral(?object))
                        }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT (COUNT(?object) AS ?objectCount)
                        WHERE {{
                          ?instance a <{subject_type}> .
                          ?instance <{subject_predicate}> ?object
                          FILTER(isLiteral(?object))
                        }}"""
            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _count_query(self) -> str:
        if self.subject_type is None:
            query = """SELECT (COUNT(?object) AS ?objectCount)
                WHERE {{
                  ?instance <{subject_predicate}> ?object
                  FILTER(isIRI(?object))
                }}"""
            return query.format(subject_predicate=self.subject_predicate)
        else:
            query = """SELECT (COUNT(?object) AS ?objectCount)
                        WHERE {{
                          ?instance a <{subject_type}> .
                          ?instance <{subject_predicate}> ?object
                          FILTER(isIRI(?object))
                        }}"""

            return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        instance, object_entity = cast(tuple[URIRef, URIRef], query_result_row)
        value = remove_namespace_from_uri(object_entity)

        row_output.add_triples.append((instance, self.subject_predicate, rdflib.Literal(value)))
        row_output.remove_triples.append((instance, self.subject_predicate, object_entity))
        row_output.instances_modified_count += 1

        return row_output
