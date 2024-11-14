from typing import cast
from urllib.parse import quote

from rdflib import Graph, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models._rdfpath import RDFPath, SingleProperty
from cognite.neat._rules.models.information import InformationRules
from cognite.neat._shared import Triple
from cognite.neat._utils.rdf_ import add_triples_in_batch, remove_namespace_from_uri

from ._base import BaseTransformer


class ReduceHopTraversal(BaseTransformer):
    """ReduceHopTraversal is a transformer that reduces the number of hops to direct connection."""

    ...


class AddSelfReferenceProperty(BaseTransformer):
    description: str = "Adds property that contains id of reference to all references of given class in Rules"
    _use_only_once: bool = True
    _need_changes = frozenset({})
    _ref_template: str = """SELECT ?s WHERE {{?s a <{type_}>}}"""

    def __init__(
        self,
        rules: InformationRules,
    ):
        self.rules = rules
        self.properties = InformationAnalysis(rules).all_reference_transformations()

    def transform(self, graph: Graph) -> None:
        for property_ in self.properties:
            prefix = property_.transformation.traversal.class_.prefix
            suffix = property_.transformation.traversal.class_.suffix

            namespace = self.rules.prefixes[prefix] if prefix in self.rules.prefixes else self.rules.metadata.namespace

            for (reference,) in graph.query(self._ref_template.format(type_=namespace[suffix])):  # type: ignore [misc]
                graph.add(
                    (
                        reference,
                        self.rules.metadata.namespace[property_.property_],
                        reference,
                    )
                )

            traversal = SingleProperty.from_string(
                class_=property_.class_.id,
                property_=f"{self.rules.metadata.prefix}:{property_.property_}",
            )

            property_.transformation = RDFPath(traversal=traversal)


class MakeConnectionOnExactMatch(BaseTransformer):
    description: str = "Adds property that contains id of reference to all references of given class in Rules"
    _use_only_once: bool = True
    _need_changes = frozenset({})
    _ref_template: str = """SELECT DISTINCT ?subject ?object
                            WHERE {{
                                ?subject a <{subject_type}> .
                                ?subject <{subject_predicate}> ?value .
                                ?object <{object_predicate}> ?value .
                                ?object a <{object_type}> .
                            }}"""

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

        self.connection = (
            DEFAULT_NAMESPACE[quote(connection.strip())]
            if isinstance(connection, str)
            else connection or DEFAULT_NAMESPACE[remove_namespace_from_uri(self.object_type).lower()]
        )

        self.limit = limit

    def transform(self, graph: Graph) -> None:
        query = self._ref_template.format(
            subject_type=self.subject_type,
            subject_predicate=self.subject_predicate,
            object_type=self.object_type,
            object_predicate=self.object_predicate,
        )

        if self.limit and isinstance(self.limit, int) and self.limit > 0:
            query += f" LIMIT {self.limit}"

        triples: list[Triple] = []
        for subject, object in graph.query(query):  # type: ignore [misc]
            triples.append(cast(Triple, (subject, self.connection, object)))

        print(f"Found {len(triples)} connections. Adding them to the graph...")
        add_triples_in_batch(graph, triples)
