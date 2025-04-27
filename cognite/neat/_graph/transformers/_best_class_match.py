from rdflib import URIRef
from rdflib.query import ResultRow

from ._base import BaseTransformerStandardised, RowTransformationOutput


class BestClassMatch(BaseTransformerStandardised):
    description = (
        "Set the RDF.type of an instance based minimizing the properties lost if the instances is written to the class"
    )

    def __init__(self, classes: dict[URIRef, frozenset[str]]) -> None:
        self.classes = classes

    def _count_query(self) -> str:
        raise NotImplementedError()

    def _skip_count_query(self) -> str:
        raise NotImplementedError()

    def _iterate_query(self) -> str:
        raise NotImplementedError()

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        raise NotImplementedError()
