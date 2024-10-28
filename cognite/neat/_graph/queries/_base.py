import warnings
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, cast, overload

from rdflib import RDF, Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.query import ResultRow

from cognite.neat._constants import UNKNOWN_TYPE
from cognite.neat._graph.models import InstanceType
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationRules
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

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

    def triples_of_type_instances(self, rdf_type: str | URIRef) -> list[tuple[str, str, str]]:
        """Get all triples of a given type.

        This method assumes the graph has been transformed into the default namespace.
        """
        if isinstance(rdf_type, URIRef):
            rdf_uri = rdf_type
        elif isinstance(rdf_type, str) and self.rules:
            rdf_uri = self.rules.metadata.namespace[rdf_type]
        else:
            warnings.warn(
                "Unknown namespace. Please either provide a URIRef or set the rules of the store.",
                stacklevel=2,
            )
            return []

        query = (
            "SELECT ?instance ?prop ?value "
            f"WHERE {{ ?instance a <{rdf_uri}> . ?instance ?prop ?value . }} "
            "order by ?instance"
        )

        result = self.graph.query(query)

        # We cannot include the RDF.type in case there is a neat:type property
        return [remove_namespace_from_uri(list(triple)) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index, arg-type]

    def types_with_property(self, property_uri: URIRef) -> list[URIRef]:
        """Check if a property exists in the graph store

        Args:
            property_uri: Property URI to check

        Returns:
            True if property exists, False otherwise
        """
        query = f"SELECT DISTINCT ?t WHERE {{ ?s <{property_uri}> ?o ; a ?t}} Limit 1"
        return cast(list[URIRef], [t[0] for t in self.graph.query(query)])  # type: ignore[index]

    def has_namespace(self, namespace: Namespace) -> bool:
        """Check if a namespace exists in the graph store

        Args:
            namespace: Namespace to check

        Returns:
            True if namespace exists, False otherwise
        """
        query = f"ASK WHERE {{ ?s ?p ?o . FILTER(STRSTARTS(STR(?p), STR(<{namespace}>))) }}"
        return bool(self.graph.query(query))

    def has_type(self, type_: URIRef) -> bool:
        """Check if a type exists in the graph store

        Args:
            type_: Type to check

        Returns:
            True if type exists, False otherwise
        """
        query = f"ASK WHERE {{ ?s a <{type_}> }}"
        return bool(self.graph.query(query))

    def describe(
        self,
        instance_id: URIRef,
        instance_type: str | None = None,
        property_renaming_config: dict | None = None,
        property_types: dict[str, EntityTypes] | None = None,
    ) -> tuple[str, dict[str | InstanceType, list[str]]] | None:
        """DESCRIBE instance for a given class from the graph store

        Args:
            instance_id: Instance id for which we want to generate query
            instance_type: Type of the instance, default None (will be inferred from triples)
            property_renaming_config: Dictionary to rename properties, default None (no renaming)
            property_types: Dictionary of property types, default None (helper for removal of namespace)


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

            # set property
            if property_renaming_config and predicate != RDF.type:
                property_ = property_renaming_config.get(
                    predicate, remove_namespace_from_uri(predicate, validation="prefix")
                )
            elif not property_renaming_config and predicate != RDF.type:
                property_ = remove_namespace_from_uri(predicate, validation="prefix")
            else:
                property_ = RDF.type

            # set value
            # if it is URIRef and property type is object property, we need to remove namespace
            # if it URIref but we are doing this into data type property, we do not remove namespace
            # case 1 for RDF type we remove namespace
            if property_ == RDF.type:
                value = remove_namespace_from_uri(object_, validation="prefix")

            # case 2 for define object properties we remove namespace
            elif (
                isinstance(object_, URIRef)
                and property_types
                and property_types.get(property_, None) == EntityTypes.object_property
            ):
                value = remove_namespace_from_uri(object_, validation="prefix")

            # case 3 when property type is not defined and returned value is URIRef we remove namespace
            elif isinstance(object_, URIRef) and not property_types:
                value = remove_namespace_from_uri(object_, validation="prefix")

            # case 4 for data type properties we do not remove namespace but keep the entire value
            # but we drop the datatype part, and keep everything to be string (data loader will do the conversion)
            # for value type it expects (if possible)
            else:
                value = str(object_)

            # add type to the dictionary
            if predicate != RDF.type:
                property_values[property_].append(value)
            else:
                # guarding against multiple rdf:type values as this is not allowed in CDF
                if RDF.type not in property_values:
                    property_values[RDF.type].append(instance_type if instance_type else value)
                else:
                    # we should not have multiple rdf:type values
                    continue

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

    def multi_value_type_property(
        self,
    ) -> Iterable[tuple[URIRef, URIRef, list[URIRef]]]:
        query = """SELECT ?sourceType ?property
                          (GROUP_CONCAT(DISTINCT STR(?valueType); SEPARATOR=",") AS ?valueTypes)

                   WHERE {{
                       ?s ?property ?o .
                       ?s a ?sourceType .
                       OPTIONAL {{ ?o a ?type }}

                       # Key part to determine value type: either object, data or unknown
                       BIND(   IF(isLiteral(?o),DATATYPE(?o),
                               IF(BOUND(?type), ?type,
                                               <{unknownType}>)) AS ?valueType)
                   }}

                   GROUP BY ?sourceType ?property
                   HAVING (COUNT(DISTINCT ?valueType) > 1)"""

        for (
            source_type,
            property_,
            value_types,
        ) in cast(
            ResultRow,
            self.graph.query(query.format(unknownType=str(UNKNOWN_TYPE))),
        ):
            yield cast(URIRef, source_type), cast(URIRef, property_), [URIRef(uri) for uri in value_types.split(",")]
