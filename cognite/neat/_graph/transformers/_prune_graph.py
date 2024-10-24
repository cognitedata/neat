from rdflib import Graph, Namespace, URIRef
from rdflib.query import ResultRow
from rdflib.term import Identifier

from ._base import BaseTransformer


# TODO: Handle the cse when value is None, which will not make the TextObject resolve
class TwoHopFlattener(BaseTransformer):
    """
    Transformer that will flatten the distance between a source node, an intermediate connecting node, and a
    target property that is connected to the intermediate node.
    The transformation result is that the target property is attached directly to the source node, instead of having
    to go via the intermediate node.
    The user can also provide a flag to decide if the intermediate node should be removed from the graph or not
    after connecting the target property to the source node.

        Ex. TwoHopFlattener:

        Graph before flattening (with deletion of intermediate node):
        node(A, rdf:type(Pump)) -(predicate("vendor"))>
                                node(B, rdf:type(TextObject)) -(predicate("value"))> Literal("CompanyX")

        Graph after flattening nodes with destination_node_type = rdf:type(TextObject), property_predicate = :value,
        and property_name = "value":

        node(A, rdf:type(Pump)) -(predicate("vendor"))> Literal("CompanyX")

    Args:
        destination_node_type: RDF.type of edge Node
        property_predicate: Predicate to use when resolving the value from the edge node
        property_name: name of the property that the intermediate node is pointing to
        delete_connecting_node: bool if the intermediate Node and Edge between source Node
                                and target property should be deleted. Defaults to True.
    """

    description: str = "Prunes the graph of specified node types that do not have connections to other nodes."
    _query_template: str = """SELECT ?sourceNode ?property ?destinationNode ?value WHERE {{
                                     ?sourceNode ?property ?destinationNode .
                                     ?destinationNode a <{destination_node_type}> .
                                     ?destinationNode <{property_predicate}> ?{property_name} . }}"""

    def __init__(
        self,
        destination_node_type: URIRef,
        property_predicate: Namespace,
        property_name: str,
        delete_connecting_node: bool = True,
    ):
        self.destination_node_type = destination_node_type
        self.property_predicate = property_predicate
        self.property_name = property_name
        self.delete_connecting_node = delete_connecting_node

    def transform(self, graph: Graph) -> None:
        nodes_to_delete: list[Identifier] = []

        graph_traversals = list(
            graph.query(
                self._query_template.format(
                    destination_node_type=self.destination_node_type,
                    property_predicate=self.property_predicate,
                    property_name=self.property_name,
                )
            )
        )

        for path in graph_traversals:
            if isinstance(path, ResultRow):
                source_node, predicate, destination_node, property_value = path.asdict().values()

                # Create new connection from source node to value
                graph.add((source_node, predicate, property_value))
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
                if isinstance(node, ResultRow):
                    graph.remove(triple=(node["subject"], None, None))
