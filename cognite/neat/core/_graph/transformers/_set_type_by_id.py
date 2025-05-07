from rdflib import URIRef
from rdflib.query import ResultRow

from ._base import BaseTransformerStandardised, RowTransformationOutput


class SetRDFTypeById(BaseTransformerStandardised):
    """This transformer sets the RDF.type of instances based on the provided mapping of instance IDs to RDF types.

    Args:
        type_by_id (dict[str, URIRef]): A dictionary where the key is the instance ID and the value is the RDF type.
            The instance IDs are represented as strings, and the RDF types are represented as URIRef objects.

    """

    description = "Set the RDF.type given the instance ID."

    def __init__(self, type_by_id: dict[str, URIRef]) -> None:
        self.type_by_id = type_by_id

    def _count_query(self) -> str:
        """Count the number of instances."""
        return """SELECT (COUNT(?instance) AS ?instanceCount)
                WHERE { ?instance a ?type}"""

    def _iterate_query(self) -> str:
        return """SELECT ?instance ?type WHERE {?instance a ?type}"""

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        raise NotImplementedError()
