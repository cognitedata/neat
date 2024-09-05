import warnings
from collections import defaultdict
from typing import Literal, cast, overload

from rdflib import RDF, Graph, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.query import ResultRow

from cognite.neat.graph.models import InstanceType
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import InformationRules
from cognite.neat.utils.rdf_ import remove_namespace_from_uri

from ._construct import build_construct_query


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(self, graph: Graph, rules: InformationRules | None = None):
        self.graph = graph
        self.rules = rules

    def summarize_instances(self) -> list[tuple]:
        """Summarize instances in the graph store by class and count"""

        query_statement = """ SELECT ?class (COUNT(?instance) AS ?instanceCount)
                             WHERE {
                             ?instance a ?class .
                             }
                             GROUP BY ?class
                             ORDER BY DESC(?instanceCount) """

        return [
            (
                remove_namespace_from_uri(cast(URIRef, cast(tuple, res)[0])),
                cast(RdfLiteral, cast(tuple, res)[1]).value,
            )
            for res in list(self.graph.query(query_statement))
        ]

    def list_instances_ids_of_class(self, class_uri: URIRef, limit: int = -1) -> list[URIRef]:
        """Get instances ids for a given class

        Args:
            class_uri: Class for which instances are to be found
            limit: Max number of instances to return, by default -1 meaning all instances

        Returns:
            List of class instance URIs
        """
        query_statement = "SELECT DISTINCT ?subject WHERE { ?subject a <class> .} LIMIT X".replace(
            "class", class_uri
        ).replace("LIMIT X", "" if limit == -1 else f"LIMIT {limit}")
        return [cast(tuple, res)[0] for res in list(self.graph.query(query_statement))]

    def list_instances_of_type(self, class_uri: URIRef) -> list[ResultRow]:
        """Get all triples for instances of a given class

        Args:
            class_uri: Class for which instances are to be found

        Returns:
            List of triples for instances of the given class
        """
        query = (
            f"SELECT ?instance ?prop ?value "
            f"WHERE {{ ?instance rdf:type <{class_uri}> . ?instance ?prop ?value . }} order by ?instance "
        )

        # Select queries gives an iterable of result rows
        return cast(list[ResultRow], list(self.graph.query(query)))

    def triples_of_type_instances(self, rdf_type: str) -> list[tuple[str, str, str]]:
        """Get all triples of a given type.

        This method assumes the graph has been transformed into the default namespace.
        """

        if self.rules:
            query = (
                f"SELECT ?instance ?prop ?value "
                f"WHERE {{ ?instance a <{self.rules.metadata.namespace[rdf_type]}> . ?instance ?prop ?value . }} "
                "order by ?instance"
            )

            result = self.graph.query(query)

            # We cannot include the RDF.type in case there is a neat:type property
            return [remove_namespace_from_uri(*triple) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index]
        else:
            warnings.warn(
                "No rules found for the graph store, returning empty list.",
                stacklevel=2,
            )
            return []

    def describe(
        self,
        instance_id: URIRef,
        property_renaming_config: dict | None = None,
    ) -> tuple[str, dict[str | InstanceType, list[str]]] | None:
        """DESCRIBE instance for a given class from the graph store

        Args:
            instance_id: Instance id for which we want to generate query
            property_renaming_config: Dictionary to rename properties, default None

        Returns:
            Dictionary of instance properties
        """
        property_values: dict[str, list[str]] = defaultdict(list)
        identifier = remove_namespace_from_uri(instance_id, validation="prefix")
        for _, predicate, object_ in cast(list[ResultRow], self.graph.query(f"DESCRIBE <{instance_id}>")):
            if object_.lower() in [
                "",
                "none",
                "nan",
                "null",
            ]:
                continue
            # we are skipping deep validation with Pydantic to remove namespace here
            # as it reduces time to process triples by 10-15x
            value = remove_namespace_from_uri(object_, validation="prefix")

            # use-case: calling describe without renaming properties
            # losing the namespace from the predicate!
            if not property_renaming_config and predicate != RDF.type:
                property_values[remove_namespace_from_uri(predicate, validation="prefix")].append(value)
            elif predicate == RDF.type:
                property_values[RDF.type].append(value)
            # use-case: calling describe with renaming properties
            # renaming the property to the new name, if the property is defined
            # in the RULES sheet
            elif property_renaming_config and (property_ := property_renaming_config.get(predicate, None)):
                property_values[property_].append(value)

        if property_values:
            return (
                identifier,
                property_values,
            )
        else:
            return None

    def construct_instances_of_class(
        self,
        class_: str,
        properties_optional: bool = True,
        instance_id: URIRef | None = None,
    ) -> list[tuple[str, str, str]]:
        """CONSTRUCT instances for a given class from the graph store

        Args:
            class_: Class entity for which we want to generate query
            properties_optional: Whether to make all properties optional, default True
            instance_ids: List of instance ids to filter on, default None (all)

        Returns:
            List of triples for instances of the given class
        """

        if self.rules and (
            query := build_construct_query(
                class_=ClassEntity(prefix=self.rules.metadata.prefix, suffix=class_),
                graph=self.graph,
                rules=self.rules,
                properties_optional=properties_optional,
                instance_id=instance_id,
            )
        ):
            result = self.graph.query(query)

            # We cannot include the RDF.type in case there is a neat:type property
            return [remove_namespace_from_uri(cast(ResultRow, triple)) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index]
        else:
            warnings.warn(
                "No rules found for the graph store, returning empty list.",
                stacklevel=2,
            )
            return []

    def list_triples(self, limit: int = 25) -> list[ResultRow]:
        """List triples in the graph store

        Args:
            limit: Max number of triples to return, by default 25

        Returns:
            List of triples
        """
        query = f"SELECT ?subject ?predicate ?object WHERE {{ ?subject ?predicate ?object }} LIMIT {limit}"
        return cast(list[ResultRow], list(self.graph.query(query)))

    @overload
    def list_types(self, remove_namespace: Literal[False] = False, limit: int = 25) -> list[ResultRow]: ...

    @overload
    def list_types(self, remove_namespace: Literal[True], limit: int = 25) -> list[str]: ...

    def list_types(self, remove_namespace: bool = False, limit: int = 25) -> list[ResultRow] | list[str]:
        """List types in the graph store

        Args:
            limit: Max number of types to return, by default 25
            remove_namespace: Whether to remove the namespace from the type, by default False

        Returns:
            List of types
        """
        query = f"SELECT DISTINCT ?type WHERE {{ ?subject a ?type }} LIMIT {limit}"
        result = cast(list[ResultRow], list(self.graph.query(query)))
        if remove_namespace:
            return [remove_namespace_from_uri(res[0]) for res in result]
        return result
