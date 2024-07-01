import warnings
from typing import cast

from rdflib import RDF, Graph, URIRef
from rdflib.query import ResultRow

from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import InformationRules
from cognite.neat.utils.utils import remove_namespace

from ._construct import build_construct_query


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(self, graph: Graph, rules: InformationRules | None = None):
        self.graph = graph
        self.rules = rules

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
            return [remove_namespace(*triple) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index]
        else:
            warnings.warn("No rules found for the graph store, returning empty list.", stacklevel=2)
            return []

    def construct_instances_of_class(self, class_: str, properties_optional: bool = True) -> list[tuple[str, str, str]]:
        """CONSTRUCT instances for a given class from the graph store

        Args:
            class_: Class entity for which we want to generate query
            properties_optional: Whether to make all properties optional, default True

        Returns:
            List of triples for instances of the given class
        """

        if self.rules and (
            query := build_construct_query(
                ClassEntity(prefix=self.rules.metadata.prefix, suffix=class_),
                self.graph,
                self.rules,
                properties_optional,
            )
        ):
            result = self.graph.query(query)

            # We cannot include the RDF.type in case there is a neat:type property
            return [remove_namespace(*triple) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index]
        else:
            warnings.warn("No rules found for the graph store, returning empty list.", stacklevel=2)
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

    def list_types(self, limit: int = 25) -> list[ResultRow]:
        """List types in the graph store

        Args:
            limit: Max number of types to return, by default 25

        Returns:
            List of types
        """
        query = f"SELECT DISTINCT ?type WHERE {{ ?subject a ?type }} LIMIT {limit}"
        return cast(list[ResultRow], list(self.graph.query(query)))
