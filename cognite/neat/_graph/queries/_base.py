from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, cast, overload

from rdflib import RDF, Dataset, Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.query import ResultRow

from cognite.neat._constants import NEAT
from cognite.neat._shared import InstanceType
from cognite.neat._utils.rdf_ import remove_instance_ids_in_batch, remove_namespace_from_uri


class Queries:
    """Helper class for storing standard queries for the graph store."""

    def __init__(
        self,
        dataset: Dataset,
        default_named_graph: URIRef | None = None,
    ):
        self.dataset = dataset
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

    def properties_by_type(self, named_graph: URIRef | None = None) -> dict[URIRef, dict[URIRef, str]]:
        """Properties and their short form in the graph by type

        Args:
            named_graph: Named graph to query over, default None (default graph)

        """
        query = """SELECT DISTINCT ?type ?property
               WHERE {?s a ?type . ?s ?property ?o . FILTER(?property != rdf:type)}"""
        properties_by_type: dict[URIRef, dict[URIRef, str]] = defaultdict(dict)
        for type_, property_ in cast(ResultRow, list(self.graph(named_graph).query(query))):
            properties_by_type[type_][property_] = remove_namespace_from_uri(property_)  # type: ignore[index]
        return properties_by_type

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
        instance_type: URIRef | None = None,
        property_renaming_config: dict | None = None,
        named_graph: URIRef | None = None,
    ) -> tuple[str, dict[str | InstanceType, list[str]]] | None:
        """DESCRIBE instance for a given class from the graph store

        Args:
            instance_id: Instance id for which we want to generate query
            instance_type: Type of the instance, default None (will be inferred from triples)
            property_renaming_config: Dictionary to rename properties, default None (no renaming)
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
                    property_values[RDF.type].append(
                        remove_namespace_from_uri(instance_type, validation="prefix") if instance_type else value
                    )
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
        limit: int | None = 25,
        named_graph: URIRef | None = None,
    ) -> list[ResultRow] | list[str]:
        """List types in the graph store

        Args:
            limit: Max number of types to return, by default 25
            remove_namespace: Whether to remove the namespace from the type, by default False

        Returns:
            List of types
        """
        query = "SELECT DISTINCT ?type WHERE { ?subject a ?type }"
        if limit is not None:
            query += f" LIMIT {limit}"
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

    def count_of_type(self, class_uri: URIRef, named_graph: URIRef | None = None) -> int:
        query = f"SELECT (COUNT(?instance) AS ?instanceCount) WHERE {{ ?instance a <{class_uri}> }}"
        return int(next(iter(self.graph(named_graph).query(query)))[0])  # type: ignore[arg-type, index]

    def list_instances_ids_by_space(
        self, space_property: URIRef, named_graph: URIRef | None = None
    ) -> Iterable[tuple[URIRef, str]]:
        """Returns instance ids by space"""
        query = f"""SELECT DISTINCT ?instance ?space
                   WHERE {{?instance <{space_property}> ?space}}"""

        for result in cast(Iterable[ResultRow], self.graph(named_graph).query(query)):
            instance_id, space = cast(tuple[URIRef, URIRef | RdfLiteral], result)
            if isinstance(space, URIRef):
                yield instance_id, remove_namespace_from_uri(space)
            elif isinstance(space, RdfLiteral):
                yield instance_id, str(space.toPython())
            else:
                yield instance_id, str(space)
