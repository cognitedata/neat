from rdflib import Graph, Namespace, URIRef

from cognite.neat.graph.extractors import IODDExtractor

from ._base import BaseTransformer


class ResolveValues(BaseTransformer):
    """
    Knowledge graph value resolver. The transformer will search the graph to find specified source nodes that have a
    connection to specified destination nodes, and then resolve the value property attached to the destination node and
    link it directly to the source node. The result is that the intermediate node to get to the value of the property
    can be removed.
    The user can also provide a flag to decide if the intermediate node should be removed or not after performing
    the mapping from source node to the final property value.

        Ex. ResolveValues:

        Graph before pruning:
        node(A, rdf:type(Pump)) -(predicate("vendor"))>
                                node(B, rdf:type(TextObject)) -(predicate("value"))> Literal("CompanyX")

        Graph after resolving values between nodes rd:type(Pump) and rdf:type(Disc):

        node(A, rdf:type(Pump)) -(predicate("vendor"))> Literal("CompanyX")

    Args:
        destination_node_type: RDF.type of edge Node
        property_value: Predicate to use when resolving the value from the edge node
        delete_connecting_node: bool if the intermediate Node and Edge between source Node
                                and resolved value should be deleted. Defaults to True
    """

    description: str = "Prunes the graph of specified node types that do not have connections to other nodes."
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(IODDExtractor.__name__),
        }
    )
    _query_template: str = """SELECT ?sourceNode ?property ?destinationNode ?value WHERE {{
                                     ?sourceNode ?property ?destinationNode .
                                     ?destinationNode a <{destination_node_type}> .
                                     ?destinationNode <{value_property}> ?value . }}"""

    def __init__(
        self,
        destination_node_type: URIRef,
        property_value: Namespace,
        delete_connecting_node: bool = True,
    ):
        self.destination_node_type = destination_node_type
        self.property_value = property_value
        self.delete_connecting_node = delete_connecting_node

    def transform(self, graph: Graph) -> None:
        nodes_to_delete: list[URIRef] = []

        graph_traversals = list(
            graph.query(
                self._query_template.format(
                    destination_node_type=self.destination_node_type, value_property=self.property_value
                )
            )
        )

        for path in graph_traversals:
            source_node, predicate, destination_node, value_property = path.asdict().values()

            # Create new connection from source node to value
            graph.add((source_node, predicate, value_property))
            nodes_to_delete.append(destination_node)

        if self.delete_connecting_node:
            for node in nodes_to_delete:
                # Remove edge triples to node
                graph.remove((None, None, node))
                # Remove node triple
                graph.remove((node, None, None))


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

    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."
    _need_changes = frozenset(
        {
            str(IODDExtractor.__name__),
        }
    )
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
        for object_type in self.node_prune_types:
            nodes_without_neighbours = list(graph.query(self._query_template.format(rdf_type=object_type)))

            for node in nodes_without_neighbours:
                # Remove node and its property triples in the graph
                graph.remove(triple=(node["subject"], None, None))
