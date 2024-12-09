from typing import cast

from rdflib import Graph, Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._shared import Triple
from cognite.neat._utils.rdf_ import as_neat_compliant_uri
from cognite.neat._utils.text import sentence_or_string_to_camel

from ._base import BaseTransformer


class AttachPropertyFromTargetToSource(BaseTransformer):
    """
    Transformer that considers a TargetNode and SourceNode relationship, to extract a property that is attached to
    the TargetNode, and attaches it to the SourceNode instead, while also deleting the edge between
    the SourceNode and TargetNode.
    This means that you no longer have to go via the SourceNode to TargetNode to extract
    the desired property from TargetNode, you can get it directly from the SourceNode instead.
    Further, there are two ways of defining the predicate for the new property to attach to
    the SourceNode. The predicate that is used will either be the old predicate between the SourceNode and TargetNode,
    or, the TargetNode may hold a property with a value for the new predicate to use.
    In this case, the user must specify the name of this predicate property connected to the TargetNode.
    Consider the following example for illustration:

        Ex. AttachPropertyFromTargetToSource
        Graph before transformation:

            :SourceNode a :SourceType .
            :SourceNode :sourceProperty :TargetNode .

            :TargetNode a :TargetType .
            :TargetNode :propertyWhichValueWeWant 'Target Value' .
            :TargetNode :propertyWhichValueWeMightWantAsNameForNewProperty 'PropertyName'

        Use case A after transformation - attach new property to SourceNode using old predicate:

            :SourceNode a :SourceType .
            :SourceNode :sourceProperty 'Target Value' .

        Use case B after transformation - extract new predicate from one of the properties of the TargetNode:

            :SourceNode a :SourceType .
            :SourceNode :PropertyName 'Target Value' .


    The user can provide a flag to decide if the intermediate target node should be removed from the graph or not
    after connecting the target property to the source node. The example illustrates this.
    The default however is False.

    If delete_target_node is not set, the expected number of triples after this transformation should be the same as
    before the transformation.

    If delete_target_node is set, the expected number of triples should be:
        #triples_before - #target_nodes * #target_nodes_properties

        Number of triples after operation from above example: 5 - 1*3 = 2

    Args:
        target_node_type: RDF.type of edge Node
        target_property: URIRef of the property that holds the value attached to the intermediate node
        target_property_holding_new_property: URIRef of the property which value will be new
        property that will be added to the source node
        delete_target_node: bool if the intermediate Node and Edge between source Node
                                and target property should be deleted. Defaults to False.
        convert_literal_to_uri: bool if the value of the new property should be converted to URIRef. Defaults to False.
        namespace: Namespace to use when converting value to URIRef. Defaults to DEFAULT_NAMESPACE.
    """

    description: str = "Attaches a target property from a target node that is connected to a source node."

    _query_template_use_case_a: str = """
    SELECT ?sourceNode ?sourceProperty ?targetNode ?newSourceProperty ?newSourcePropertyValue WHERE {{
        ?sourceNode ?sourceProperty ?targetNode .
        BIND( <{target_property}> as ?newSourceProperty ) .
        ?targetNode a <{target_node_type}> .
        ?targetNode <{target_property}> ?newSourcePropertyValue . }}"""

    _query_template_use_case_b: str = """
    SELECT ?sourceNode ?sourceProperty ?targetNode ?newSourceProperty ?newSourcePropertyValue WHERE {{
        ?sourceNode ?sourceProperty ?targetNode .
        ?targetNode a <{target_node_type}> .
        ?targetNode <{target_property_holding_new_property_name}> ?newSourceProperty .
        ?targetNode <{target_property}> ?newSourcePropertyValue . }}"""

    def __init__(
        self,
        target_node_type: URIRef,
        target_property: URIRef,
        target_property_holding_new_property: URIRef | None = None,
        delete_target_node: bool = False,
        convert_literal_to_uri: bool = False,
        namespace: Namespace | None = None,
    ):
        self.target_node_type = target_node_type
        self.target_property = target_property
        self.delete_target_node = delete_target_node
        self.target_property_holding_new_property = target_property_holding_new_property
        self.convert_literal_to_uri = convert_literal_to_uri
        self.namespace = namespace or DEFAULT_NAMESPACE

    def transform(self, graph) -> None:
        nodes_to_delete: list[tuple] = []

        if self.target_property_holding_new_property is not None:
            query = self._query_template_use_case_b.format(
                target_node_type=self.target_node_type,
                target_property_holding_new_property_name=self.target_property_holding_new_property,
                target_property=self.target_property,
            )
        else:
            query = self._query_template_use_case_a.format(
                target_node_type=self.target_node_type,
                target_property=self.target_property,
            )

        for (
            source_node,
            old_predicate,
            target_node,
            new_predicate_value,
            new_property_value,
        ) in graph.query(query):
            if self.target_property_holding_new_property is not None:
                # Ensure new predicate is URI compliant as we are creating a new predicate
                new_predicate_value_string = sentence_or_string_to_camel(str(new_predicate_value))
                predicate = as_neat_compliant_uri(self.namespace[new_predicate_value_string])
            else:
                predicate = old_predicate
            # Create new connection from source node to value
            graph.add(
                (
                    source_node,
                    predicate,
                    (self.namespace[new_property_value] if self.convert_literal_to_uri else new_property_value),
                )
            )
            # Remove old relationship between source node and destination node
            graph.remove((source_node, old_predicate, target_node))

            nodes_to_delete.append(target_node)

        if self.delete_target_node:
            for target_node in nodes_to_delete:
                # Remove triples with edges to target_node
                graph.remove((None, None, target_node))
                # Remove target node triple and its properties
                graph.remove((target_node, None, None))


class PruneDanglingNodes(BaseTransformer):
    """
    Knowledge graph pruner and resolver. Will remove rdf triples from graph that does not have connections
    to other nodes, and traverse graph for specified types to resolve the value in the final node and link it to
    the source node.

        Ex. PruneDanglingNodes

        Graph before pruning:
        node(A, rdf:type(Pump)) -> node(B, rdf:type(Disc)),
        node(C, rdf:type(Disc))

        Graph after pruning of nodes rdf:type(Disc):

        node(A, rd:type(Pump)) -> node(B, rdf:type(Disc))

    Args:
        node_prune_types: list of RDF types to prune from the Graph if they are stand-alone Nodes
    """

    description: str = "Prunes nodes of specific rdf types that do not have any connection to them."
    _query_template = """
                    SELECT ?subject
                    WHERE {{
                        ?subject a <{rdf_type}> .
                        FILTER NOT EXISTS {{ ?s ?p ?subject }}
                    }}
            """

    def __init__(
        self,
        node_prune_types: list[URIRef],
    ):
        self.node_prune_types = node_prune_types

    def transform(self, graph: Graph) -> None:
        for type_ in self.node_prune_types:
            for (subject,) in list(graph.query(self._query_template.format(rdf_type=type_))):  # type: ignore
                graph.remove((subject, None, None))


class PruneTypes(BaseTransformer):
    """
    Removes all the instances of specific type
    """

    description: str = "Prunes nodes of specific rdf types"
    _query_template = """
                        SELECT ?subject
                        WHERE {{
                            ?subject a <{rdf_type}> .
                            }}
                      """

    def __init__(
        self,
        node_prune_types: list[URIRef],
    ):
        self.node_prune_types = node_prune_types

    def transform(self, graph: Graph) -> None:
        for type_ in self.node_prune_types:
            for (subject,) in list(graph.query(self._query_template.format(rdf_type=type_))):  # type: ignore
                graph.remove((subject, None, None))


class PruneDeadEndEdges(BaseTransformer):
    """
    Removes all the triples where object is a node that is not found in graph
    """

    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."
    _query_template = """
                        SELECT ?subject ?predicate ?object
                        WHERE {
                            ?subject ?predicate ?object .
                            FILTER (isIRI(?object) && ?predicate != rdf:type)
                            FILTER NOT EXISTS {?object ?p ?o .}

                            }

                      """

    def transform(self, graph: Graph) -> None:
        for triple in graph.query(self._query_template):
            graph.remove(cast(Triple, triple))


class PruneInstancesOfUnknownType(BaseTransformer):
    """
    Removes all the triples where object is a node that is not found in graph
    """

    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."
    _query_template = """
                    SELECT DISTINCT ?subject
                    WHERE {
                        ?subject ?p ?o .
                        FILTER NOT EXISTS {?subject a ?object .}

                        }

                    """

    def transform(self, graph: Graph) -> None:
        for (subject,) in graph.query(self._query_template):  # type: ignore
            graph.remove((subject, None, None))
