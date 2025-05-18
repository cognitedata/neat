import warnings
from collections.abc import Hashable
from typing import cast

from rdflib import Literal, URIRef
from rdflib.query import ResultRow

from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._utils.rdf_ import uri_to_cdf_id

from ._base import BaseTransformerStandardised, RowTransformationOutput


class ObjectMapper(BaseTransformerStandardised):
    description = "Maps all values for a given predicate and type."

    def __init__(self, mapping: dict[Hashable, object], predicate: URIRef, type: URIRef | None = None) -> None:
        self.predicate = predicate
        self.mapping = mapping
        self.type = type

    def _count_query(self) -> str:
        """Count the number of instances."""
        filter_expression = self._get_filter_expression()

        return f"""SELECT (COUNT(?instance) AS ?instanceCount)
                WHERE {{ ?instance ?predicate ?object . FILTER({filter_expression})}}"""

    def _get_filter_expression(self) -> str:
        filter_expression = f"?predicate = <{self.predicate}>"
        if self.type is not None:
            filter_expression += f""" . ?instance a <{self.type}>"""
        return filter_expression

    def _iterate_query(self) -> str:
        filter_expression = self._get_filter_expression()
        return f"""SELECT ?instance ?object WHERE {{?instance ?predicate ?object . FILTER({filter_expression})}}"""

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        instance, current_value = cast(tuple[URIRef, Literal], query_result_row)
        new_value = self.mapping.get(current_value.toPython(), None)
        if new_value is None:
            warnings.warn(
                NeatValueWarning(
                    f"{uri_to_cdf_id(instance)} could not map "
                    f"{uri_to_cdf_id(self.predicate)}: {current_value.toPython()!r}. "
                    f"It does not exist in the given mapping."
                ),
                stacklevel=2,
            )
            return row_output
        row_output.add_triples.add((instance, self.predicate, Literal(new_value)))
        row_output.remove_triples.add((instance, self.predicate, current_value))
        row_output.instances_modified_count += 1
        return row_output
