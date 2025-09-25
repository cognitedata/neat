import warnings
from collections.abc import Callable, Iterator
from typing import Any, cast
from urllib.parse import quote

import rdflib
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat.v0.core._constants import NEAT
from cognite.neat.v0.core._issues.warnings import PropertyDataTypeConversionWarning
from cognite.neat.v0.core._utils.auxiliary import string_to_ideal_type
from cognite.neat.v0.core._utils.rdf_ import Triple, get_namespace, remove_namespace_from_uri, uri_to_cdf_id

from ._base import BaseTransformerStandardised, RowTransformationOutput


class SplitMultiValueProperty(BaseTransformerStandardised):
    description: str = (
        "SplitMultiValueProperty is a transformer that splits a "
        "multi-value property into multiple single-value properties."
    )
    _use_only_once: bool = True
    _need_changes = frozenset({})

    def __init__(self, unknown_type: URIRef | None = None) -> None:
        self.unknown_type = unknown_type or NEAT.UnknownType

    def _iterate_query(self) -> str:
        query = """SELECT ?subjectType ?property
                          (GROUP_CONCAT(DISTINCT STR(?valueType); SEPARATOR=",") AS ?valueTypes)

                   WHERE {{
                       ?s ?property ?o .
                       ?s a ?subjectType .
                       OPTIONAL {{ ?o a ?type }}

                       # Key part to determine value type: either object, data or unknown
                       BIND(   IF(isLiteral(?o),DATATYPE(?o),
                               IF(BOUND(?type), ?type,
                                               <{unknownType}>)) AS ?valueType)
                   }}

                   GROUP BY ?subjectType ?property
                   HAVING (COUNT(DISTINCT ?valueType) > 1)"""

        return query.format(unknownType=self.unknown_type)

    def _count_query(self) -> str:
        query = """SELECT (COUNT(*) AS ?tripleCount)
                   WHERE {?s ?p ?o .}"""
        return query

    def _sub_iterate_query(self, type_: URIRef, property_: URIRef) -> str:
        query = """ SELECT ?s ?p ?o ?valueType WHERE {{
                           ?s a <{subject_uri}> .
                           ?s <{property_uri}> ?o .

                           OPTIONAL {{ ?o a ?type }}

                           BIND(<{property_uri}> AS ?p)

                           BIND(IF(isLiteral(?o),  DATATYPE(?o),
                                   IF(BOUND(?type),?type,
                                                   <{unknownType}>)) AS ?valueType)

                                               }} """

        return query.format(unknownType=self.unknown_type, subject_uri=type_, property_uri=property_)

    def _iterator(self, graph: Graph) -> Iterator:
        # this method is doing some funky stuff, we should review this.
        for type_, property_, _ in graph.query(self._iterate_query()):  # type: ignore
            yield from graph.query(self._sub_iterate_query(type_, property_))  # type: ignore

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        subject, old_property, object, value_type = query_result_row

        new_property = URIRef(f"{old_property}_{remove_namespace_from_uri(value_type)}")

        row_output.add_triples.add(cast(Triple, (subject, new_property, object)))
        row_output.remove_triples.add(cast(Triple, (subject, old_property, object)))

        row_output.instances_modified_count += 1

        return row_output


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
        row_output.add_triples.add((instance, self.subject_predicate, rdflib.Literal(converted_value)))  # type: ignore[arg-type]
        row_output.remove_triples.add((instance, self.subject_predicate, literal))  # type: ignore[arg-type]
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
        row_output.add_triples.add((new_entity, RDF.type, entity_type))
        row_output.instances_added_count += 1  # we add one new entity

        if self.new_property is not None:
            row_output.add_triples.add((new_entity, namespace[self.new_property], rdflib.Literal(value)))  # type: ignore[arg-type]
            row_output.instances_modified_count += 1  # we modify the new entity

        row_output.add_triples.add((instance, self.subject_predicate, new_entity))  # type: ignore[arg-type]
        row_output.remove_triples.add((instance, self.subject_predicate, literal))  # type: ignore[arg-type]
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
        value = uri_to_cdf_id(object_entity)

        row_output.add_triples.add((instance, self.subject_predicate, rdflib.Literal(value)))
        row_output.remove_triples.add((instance, self.subject_predicate, object_entity))
        row_output.instances_modified_count += 1

        return row_output


class SetType(BaseTransformerStandardised):
    description = "Set the type of an instance based on a property"

    def __init__(
        self,
        subject_type: URIRef,
        subject_predicate: URIRef,
        drop_property: bool = False,
        namespace: Namespace | None = None,
    ) -> None:
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.drop_property = drop_property
        self._namespace = namespace or Namespace(get_namespace(subject_type))

    def _count_query(self) -> str:
        query = """SELECT (COUNT(?object) AS ?objectCount)
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?object
                      FILTER(isLiteral(?object))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _skip_count_query(self) -> str:
        query = """SELECT (COUNT(?object) AS ?objectCount)
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?object
                      FILTER(isIRI(?object))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def _iterate_query(self) -> str:
        query = """SELECT ?instance ?object
                    WHERE {{
                      ?instance a <{subject_type}> .
                      ?instance <{subject_predicate}> ?object
                      FILTER(isLiteral(?object))
                    }}"""
        return query.format(subject_type=self.subject_type, subject_predicate=self.subject_predicate)

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        instance, object_literal = cast(tuple[URIRef, Literal], query_result_row)
        if self.drop_property:
            row_output.remove_triples.add((instance, self.subject_predicate, object_literal))

        row_output.remove_triples.add((instance, RDF.type, self.subject_type))
        new_type = self._namespace[quote(object_literal.toPython())]
        row_output.add_triples.add((instance, RDF.type, new_type))
        row_output.add_triples.add((new_type, RDFS.subClassOf, self.subject_type))
        row_output.instances_modified_count += 1

        return row_output
