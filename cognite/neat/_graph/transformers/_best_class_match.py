import warnings
from collections.abc import Iterable, Iterator
from typing import cast

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.query import ResultRow

from cognite.neat._issues.warnings import NoClassFoundWarning, PartialClassFoundWarning
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._base import BaseTransformerStandardised, RowTransformationOutput


class BestClassMatch(BaseTransformerStandardised):
    """This transformer sets the RDF.type of an instance based on minimizing the missing properties
    by comparing instance properties to each class properties.

    Args:
        classes (dict[URIRef, frozenset[str]]): A dictionary where the key is the class URI and the value is a set of
            properties that belong to that class. The properties are represented as strings.

    """

    description = "Set the RDF.type based on best class match."

    def __init__(self, classes: dict[URIRef, frozenset[str]]) -> None:
        self.classes = classes

    def _count_query(self) -> str:
        """Count the number of instances."""
        return """SELECT (COUNT(?instance) AS ?instanceCount)
                WHERE { ?instance a ?type}"""

    def _iterate_query(self) -> str:
        return """SELECT ?instance WHERE {?instance a ?type}"""

    def _iterator(self, graph: Graph) -> Iterator:
        """Iterate over the instances in the graph."""
        for result in graph.query(self._iterate_query()):
            (instance,) = cast(tuple[URIRef], result)
            yield graph.query(f"DESCRIBE <{instance}>")

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        predicates_str: set[str] = set()
        existing_types: set[URIRef] = set()
        instance: URIRef | None = None
        for instance_id, predicate, object_ in cast(
            Iterable[tuple[URIRef, URIRef, URIRef | Literal]], query_result_row
        ):
            if predicate == RDF.type and isinstance(object_, URIRef):
                existing_types.add(object_)
                continue
            predicates_str.add(remove_namespace_from_uri(predicate))
            instance = instance_id

        if instance is None:
            return row_output

        results: dict[URIRef, tuple[set[str], set[str], int]] = {}
        for class_uri, class_properties in self.classes.items():
            missing_properties = predicates_str - class_properties
            matching_properties = set(class_properties & predicates_str)
            if len(matching_properties) >= 1:
                results[class_uri] = (missing_properties, matching_properties, len(class_properties))

        if not results:
            warnings.warn(NoClassFoundWarning(remove_namespace_from_uri(instance)), stacklevel=2)
            return row_output

        best_class, (min_missing_properties, matching_properties, _) = min(
            # Minimize missing properties, maximize matching properties, and minimize class size
            results.items(),
            key=lambda x: (len(x[1][0]), -len(x[1][1]), x[1][2]),
        )
        if len(min_missing_properties) > 0:
            warnings.warn(
                PartialClassFoundWarning(
                    remove_namespace_from_uri(instance),
                    remove_namespace_from_uri(best_class),
                    len(min_missing_properties),
                    frozenset(min_missing_properties),
                ),
                stacklevel=2,
            )

        for existing_type in existing_types:
            if existing_type != best_class:
                row_output.remove_triples.add((instance, RDF.type, existing_type))
        row_output.add_triples.add((instance, RDF.type, best_class))
        row_output.instances_modified_count += 1
        return row_output
