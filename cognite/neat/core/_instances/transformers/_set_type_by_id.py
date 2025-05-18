import warnings
from typing import cast

from rdflib import RDF, URIRef
from rdflib.query import ResultRow

from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._utils.rdf_ import uri_to_cdf_id

from ._base import BaseTransformerStandardised, RowTransformationOutput


class SetRDFTypeById(BaseTransformerStandardised):
    """This transformer sets the RDF.type of instances based on the provided mapping of instance IDs to RDF types.

    Args:
        type_by_id (dict[str, URIRef]): A dictionary where the key is the instance ID and the value is the RDF type.
            The instance IDs are represented as strings, and the RDF types are represented as URIRef objects.
        warn_missing_instances (bool): If True, a warning will be issued for each instance ID in the graph
            that is not found in the type_by_id mapping. Defaults to False.
    """

    description = "Set the RDF.type given the instance ID."

    def __init__(self, type_by_id: dict[str, URIRef], warn_missing_instances: bool = False) -> None:
        self.type_by_id = type_by_id
        self.warn_missing_instances = warn_missing_instances

    def _count_query(self) -> str:
        """Count the number of instances."""
        return """SELECT (COUNT(?instance) AS ?instanceCount)
                WHERE { ?instance a ?type}"""

    def _iterate_query(self) -> str:
        return """SELECT ?instance ?type WHERE {?instance a ?type}"""

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        instance_id, existing_type = cast(tuple[URIRef, URIRef], query_result_row)
        instance_id_str = uri_to_cdf_id(instance_id)
        if instance_id_str not in self.type_by_id:
            if self.warn_missing_instances:
                warnings.warn(
                    NeatValueWarning(
                        f"Cannot change type of {instance_id_str!r}. "
                        f"It is not found in the given mapping. "
                        f"Will keep type {uri_to_cdf_id(existing_type)}."
                    ),
                    stacklevel=2,
                )
            return row_output

        new_type = self.type_by_id[instance_id_str]
        if new_type == existing_type:
            warnings.warn(
                NeatValueWarning(
                    f"Type of {instance_id_str} is already {uri_to_cdf_id(existing_type)}. No change needed."
                ),
                stacklevel=2,
            )
            return row_output

        row_output.add_triples.add((instance_id, RDF.type, new_type))
        row_output.remove_triples.add((instance_id, RDF.type, existing_type))
        row_output.instances_modified_count += 1

        return row_output
