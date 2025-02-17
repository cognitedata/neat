from typing import cast
from urllib.parse import quote

from rdflib import Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat._utils.rdf_ import get_namespace, remove_namespace_from_uri

from ._base import BaseTransformerStandardised, RowTransformationOutput


class MakeConnectionOnExactMatch(BaseTransformerStandardised):
    description: str = "Adds property that contains id of reference to all references of given class in Rules"
    _use_only_once: bool = False
    _need_changes = frozenset({})

    def __init__(
        self,
        subject_type: URIRef,
        subject_predicate: URIRef,
        object_type: URIRef,
        object_predicate: URIRef,
        connection: URIRef | str | None = None,
        limit: int | None = None,
    ):
        self.subject_type = subject_type
        self.subject_predicate = subject_predicate
        self.object_type = object_type
        self.object_predicate = object_predicate
        subject_namespace = Namespace(get_namespace(subject_type))
        self.connection: URIRef = (
            subject_namespace[quote(connection.strip())]
            if isinstance(connection, str)
            else connection or subject_namespace[remove_namespace_from_uri(self.object_type).lower()]
        )

        self.limit = limit

    def _iterate_query(self) -> str:
        query = """SELECT DISTINCT ?subject ?object
                            WHERE {{
                                ?subject a <{subject_type}> ;
                                        <{subject_predicate}> ?value .
                                ?object a <{object_type}> ;
                                        <{object_predicate}> ?value .
                            }}"""

        if self.limit and isinstance(self.limit, int) and self.limit > 0:
            query += f" LIMIT {self.limit}"

        return query.format(
            subject_type=self.subject_type,
            subject_predicate=self.subject_predicate,
            object_type=self.object_type,
            object_predicate=self.object_predicate,
        )

    def _count_query(self) -> str:
        query = """SELECT (COUNT(DISTINCT ?subject) as ?count)
                    WHERE {{
                        ?subject a <{subject_type}> ;
                                <{subject_predicate}> ?value .
                        ?object a <{object_type}> ;
                                <{object_predicate}> ?value .
                    }}"""

        if self.limit and isinstance(self.limit, int) and self.limit > 0:
            query += f" LIMIT {self.limit}"

        return query.format(
            subject_type=self.subject_type,
            subject_predicate=self.subject_predicate,
            object_type=self.object_type,
            object_predicate=self.object_predicate,
        )

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()

        subject, object = cast(tuple[URIRef, URIRef], query_result_row)

        row_output.add_triples.add((subject, self.connection, object))
        row_output.instances_modified_count += 1
        return row_output
