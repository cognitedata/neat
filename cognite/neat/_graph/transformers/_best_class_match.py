import urllib.parse
import warnings
from typing import cast

from rdflib import RDF, Literal, URIRef
from rdflib.query import ResultRow

from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import humanize_collection

from ._base import BaseTransformerStandardised, RowTransformationOutput


class BestClassMatch(BaseTransformerStandardised):
    description = (
        "Set the RDF.type of an instance based minimizing the missing properties "
        "by comparing instance properties to each class properties."
    )

    def __init__(self, classes: dict[URIRef, frozenset[str]]) -> None:
        self.classes = classes

    def _count_query(self) -> str:
        """Count the number of instances."""
        return """SELECT (COUNT(?instance) AS ?instanceCount)
                WHERE {
                  ?instance a ?type .
                }"""

    def _iterate_query(self) -> str:
        return """SELECT
                    ?instance
                    (GROUP_CONCAT(DISTINCT ?predicate; separator=",") AS ?predicates)
                    (GROUP_CONCAT(DISTINCT ?type; separator=",") AS ?types)
                WHERE {
                  ?instance ?predicate ?object .
                  OPTIONAL { ?instance a ?type . }
                } GROUP BY ?instance"""

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        instance, predicates_literal, types_literal = cast(tuple[URIRef, Literal, Literal], query_result_row)

        if predicates_literal:
            predicates_str = {
                urllib.parse.unquote(remove_namespace_from_uri(predicate))
                for predicate in predicates_literal.split(",")
                if URIRef(predicate) != RDF.type
            }
        else:
            predicates_str = set()

        if types_literal:
            existing_types = {URIRef(type_) for type_ in types_literal.split(",")}
        else:
            existing_types = set()

        results: dict[URIRef, tuple[set[str], set[str]]] = {}
        for class_uri, class_properties in self.classes.items():
            missing_properties = predicates_str - class_properties
            matching_properties = set(class_properties & predicates_str)
            if len(matching_properties) >= 1:
                results[class_uri] = (missing_properties, matching_properties)

        if not results:
            warnings.warn(NeatValueWarning(f"No class match found for instance {instance}"), stacklevel=2)
            return row_output

        best_class, (min_missing_properties, matching_properties) = min(
            results.items(), key=lambda x: (len(x[0][0]), -len(x[0][1]))
        )
        if len(min_missing_properties) > 0:
            warnings.warn(
                NeatValueWarning(
                    f"Instance {remove_namespace_from_uri(instance)!r} has no class match with all properties. "
                    f"Best class match is {remove_namespace_from_uri(best_class)!r} with "
                    f"{len(min_missing_properties)} missing properties: {humanize_collection(min_missing_properties)}"
                ),
                stacklevel=2,
            )

        for existing_type in existing_types:
            if existing_type != best_class:
                row_output.remove_triples.add((instance, RDF.type, existing_type))
        row_output.add_triples.add((instance, RDF.type, best_class))
        row_output.instances_modified_count += 1
        return row_output
