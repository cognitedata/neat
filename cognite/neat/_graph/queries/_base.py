import warnings
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, cast, overload

from rdflib import RDF, Dataset, Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.query import ResultRow

from cognite.neat._constants import NEAT
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationRules
from cognite.neat._shared import InstanceType
from cognite.neat._utils.rdf_ import remove_instance_ids_in_batch, remove_namespace_from_uri

from ._construct import build_construct_query


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(
        self,
        dataset: Dataset,
        rules: dict[URIRef, InformationRules] | None = None,
        default_named_graph: URIRef | None = None,
    ):
        self.dataset = dataset
        self.rules = rules or {}
        self.default_named_graph = default_named_graph or DATASET_DEFAULT_GRAPH_ID

    def graph(self, named_graph: URIRef | None = None) -> Graph:
        """Get named graph from the dataset to query over"""
        return self.dataset.graph(named_graph or self.default_named_graph)

    def summarize_instances(self, named_graph: URIRef | None = None) -> list[tuple]:
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
            for res in list(self.graph(named_graph=named_graph).query(query_statement))
        ]

    def types(self, named_graph: URIRef | None = None) -> dict[URIRef, str]:
        """Types and their short form in the graph"""
        query = """SELECT DISTINCT ?type
                   WHERE {?s a ?type .}"""

        return {  # type: ignore[misc, index, arg-type]
            cast(URIRef, type_): remove_namespace_from_uri(cast(URIRef, type_))
            for (type_,) in list(self.graph(named_graph).query(query))
        }

    def type_uri(self, type_: str, named_graph: URIRef | None = None) -> list[URIRef]:
        """Get the URIRef of a type"""
        return [k for k, v in self.types(named_graph).items() if v == type_]

    def properties(self, named_graph: URIRef | None = None) -> dict[URIRef, str]:
        """Properties and their short form in the graph

        Args:
            named_graph: Named graph to query over, default None (default graph)

        """
        query = """SELECT DISTINCT ?property
               WHERE {?s ?property ?o . FILTER(?property != rdf:type)}"""
        return {  # type: ignore[misc, index, arg-type]
            cast(URIRef, type_): remove_namespace_from_uri(cast(URIRef, type_))
            for (type_,) in list(self.graph(named_graph).query(query))
        }

    def property_uri(self, property_: str, named_graph: URIRef | None = None) -> list[URIRef]:
        """Get the URIRef of a property

        Args:
            property_: Property to find URIRef for
            named_graph: Named graph to query over, default None (default graph)
        """
        return [k for k, v in self.properties(named_graph).items() if v == property_]

    def list_instances_ids_of_class(
        self, class_uri: URIRef, limit: int = -1, named_graph: URIRef | None = None
    ) -> list[URIRef]:
        """Get instances ids for a given class

        Args:
            class_uri: Class for which instances are to be found
            limit: Max number of instances to return, by default -1 meaning all instances
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            List of class instance URIs
        """
        query_statement = "SELECT DISTINCT ?subject WHERE { ?subject a <class> .} LIMIT X".replace(
            "class", class_uri
        ).replace("LIMIT X", "" if limit == -1 else f"LIMIT {limit}")
        return [cast(tuple, res)[0] for res in list(self.graph(named_graph).query(query_statement))]

    def list_instances_of_type(self, class_uri: URIRef, named_graph: URIRef | None = None) -> list[ResultRow]:
        """Get all triples for instances of a given class

        Args:
            class_uri: Class for which instances are to be found
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            List of triples for instances of the given class in the named graph
        """
        query = (
            f"SELECT ?instance ?prop ?value "
            f"WHERE {{ ?instance rdf:type <{class_uri}> . ?instance ?prop ?value . }} order by ?instance "
        )

        # Select queries gives an iterable of result rows
        return cast(list[ResultRow], list(self.graph(named_graph).query(query)))

    def triples_of_type_instances(
        self, rdf_type: str | URIRef, named_graph: URIRef | None = None
    ) -> list[tuple[str, str, str]]:
        """Get all triples of a given type.

        Args:
            rdf_type: Type URI to query
            named_graph: Named graph to query over, default None (default graph)
        """
        named_graph = named_graph or self.default_named_graph
        if isinstance(rdf_type, URIRef):
            rdf_uri = rdf_type
        elif isinstance(rdf_type, str) and self.rules and self.rules.get(named_graph):
            rdf_uri = self.rules[named_graph].metadata.namespace[rdf_type]
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

        result = self.graph(named_graph).query(query)

        # We cannot include the RDF.type in case there is a neat:type property
        return [remove_namespace_from_uri(list(triple)) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index, arg-type]

    def type_with_property(self, type_: URIRef, property_uri: URIRef, named_graph: URIRef | None = None) -> bool:
        """Check if a property exists in the graph store

        Args:
            type_: Type URI to check
            property_uri: Property URI to check
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            True if property exists, False otherwise
        """
        query = f"SELECT ?o WHERE {{ ?s a <{type_}> ; <{property_uri}> ?o .}} Limit 1"
        return bool(list(self.graph(named_graph).query(query)))

    def has_namespace(self, namespace: Namespace, named_graph: URIRef | None = None) -> bool:
        """Check if a namespace exists in the graph store

        Args:
            namespace: Namespace to check
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            True if namespace exists, False otherwise
        """
        query = f"ASK WHERE {{ ?s ?p ?o . FILTER(STRSTARTS(STR(?p), STR(<{namespace}>))) }}"
        return bool(self.graph(named_graph).query(query))

    def has_data(self) -> bool:
        """Check if the graph store has data"""
        return cast(bool, next(iter(self.dataset.query("ASK WHERE { ?s ?p ?o }"))))

    def has_type(self, type_: URIRef, named_graph: URIRef | None = None) -> bool:
        """Check if a type exists in the graph store

        Args:
            type_: Type to check
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            True if type exists, False otherwise
        """
        query = f"ASK WHERE {{ ?s a <{type_}> }}"
        return bool(self.graph(named_graph).query(query))

    def describe(
        self,
        instance_id: URIRef,
        instance_type: str | None = None,
        property_renaming_config: dict | None = None,
        property_types: dict[str, EntityTypes] | None = None,
        named_graph: URIRef | None = None,
    ) -> tuple[str, dict[str | InstanceType, list[str]]] | None:
        """DESCRIBE instance for a given class from the graph store

        Args:
            instance_id: Instance id for which we want to generate query
            instance_type: Type of the instance, default None (will be inferred from triples)
            property_renaming_config: Dictionary to rename properties, default None (no renaming)
            property_types: Dictionary of property types, default None (helper for removal of namespace)
            named_graph: Named graph to query over, default None (default graph)


        Returns:
            Dictionary of instance properties
        """
        property_values: dict[str, list[str]] = defaultdict(list)
        identifier = remove_namespace_from_uri(instance_id, validation="prefix")
        for _, predicate, object_ in cast(list[ResultRow], self.graph(named_graph).query(f"DESCRIBE <{instance_id}>")):
            if object_.lower() in [
                "",
                "none",
                "nan",
                "null",
            ]:
                continue

            # set property
            if property_renaming_config and predicate != RDF.type:
                property_ = remove_namespace_from_uri(predicate, validation="prefix")
                renamed_property_ = property_renaming_config.get(predicate, property_)

            elif not property_renaming_config and predicate != RDF.type:
                property_ = remove_namespace_from_uri(predicate, validation="prefix")
                renamed_property_ = property_

            else:
                property_ = RDF.type
                renamed_property_ = property_

            if isinstance(object_, URIRef):
                value = remove_namespace_from_uri(object_, validation="prefix")
            elif isinstance(object_, RdfLiteral):
                value = object_.toPython()
            else:
                # It is a blank node
                value = str(object_)

            # add type to the dictionary
            if predicate != RDF.type:
                property_values[renamed_property_].append(value)
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
        named_graph: URIRef | None = None,
    ) -> list[tuple[str, str, str]]:
        """CONSTRUCT instances for a given class from the graph store

        Args:
            class_: Class entity for which we want to generate query
            properties_optional: Whether to make all properties optional, default True
            instance_ids: List of instance ids to filter on, default None (all)
            named_graph: Named graph to query over, default None (default graph

        Returns:
            List of triples for instances of the given class
        """
        named_graph = named_graph or self.default_named_graph
        if (
            self.rules
            and self.rules.get(named_graph)
            and (
                query := build_construct_query(
                    class_=ClassEntity(
                        prefix=self.rules[named_graph].metadata.prefix,
                        suffix=class_,
                    ),
                    graph=self.graph(named_graph),
                    rules=self.rules[named_graph],
                    properties_optional=properties_optional,
                    instance_id=instance_id,
                )
            )
        ):
            result = self.graph(named_graph).query(query)

            # We cannot include the RDF.type in case there is a neat:type property
            return [remove_namespace_from_uri(cast(ResultRow, triple)) for triple in result if triple[1] != RDF.type]  # type: ignore[misc, index, arg-type]
        else:
            warnings.warn(
                "No rules found for the graph store, returning empty list.",
                stacklevel=2,
            )
            return []

    def list_triples(self, limit: int = 25, named_graph: URIRef | None = None) -> list[ResultRow]:
        """List triples in the graph store

        Args:
            limit: Max number of triples to return, by default 25
            named_graph: Named graph to query over, default None (default graph)

        Returns:
            List of triples
        """
        query = f"SELECT ?subject ?predicate ?object WHERE {{ ?subject ?predicate ?object }} LIMIT {limit}"
        return cast(list[ResultRow], list(self.graph(named_graph).query(query)))

    @overload
    def list_types(self, remove_namespace: Literal[False] = False, limit: int = 25) -> list[ResultRow]: ...

    @overload
    def list_types(
        self,
        remove_namespace: Literal[True],
        limit: int = 25,
        named_graph: URIRef | None = None,
    ) -> list[str]: ...

    def list_types(
        self,
        remove_namespace: bool = False,
        limit: int = 25,
        named_graph: URIRef | None = None,
    ) -> list[ResultRow] | list[str]:
        """List types in the graph store

        Args:
            limit: Max number of types to return, by default 25
            remove_namespace: Whether to remove the namespace from the type, by default False

        Returns:
            List of types
        """
        query = f"SELECT DISTINCT ?type WHERE {{ ?subject a ?type }} LIMIT {limit}"
        result = cast(list[ResultRow], list(self.graph(named_graph).query(query)))
        if remove_namespace:
            return [remove_namespace_from_uri(res[0]) for res in result]
        return result

    def multi_value_type_property(
        self,
        named_graph: URIRef | None = None,
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
            self.graph(named_graph).query(query.format(unknownType=str(NEAT.UnknownType))),
        ):
            yield cast(URIRef, source_type), cast(URIRef, property_), [URIRef(uri) for uri in value_types.split(",")]

    def drop_types(
        self,
        type_: list[URIRef],
        named_graph: URIRef | None = None,
    ) -> dict[URIRef, int]:
        """Drop types from the graph store

        Args:
            type_: List of types to drop
            named_graph: Named graph to query over, default None (default graph

        Returns:
            Dictionary of dropped types
        """
        dropped_types: dict[URIRef, int] = {}
        for t in type_:
            instance_ids = self.list_instances_ids_of_class(t)
            dropped_types[t] = len(instance_ids)
            remove_instance_ids_in_batch(self.graph(named_graph), instance_ids)
        return dropped_types

    def multi_type_instances(self, named_graph: URIRef | None = None) -> dict[str, list[str]]:
        """Find instances with multiple types

        Args:
            named_graph: Named graph to query over, default None (default graph)

        """

        query = """
        SELECT ?instance (GROUP_CONCAT(str(?type); SEPARATOR=",") AS ?types)
        WHERE {
            ?instance a ?type .
        }
        GROUP BY ?instance
        HAVING (COUNT(?type) > 1)
        """

        result = {}
        for instance, types in self.graph(named_graph).query(query):  # type: ignore
            result[remove_namespace_from_uri(instance)] = remove_namespace_from_uri(types.split(","))

        return result
