from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.term import Node

from ._base import BaseTransformer


class ResolveValues(BaseTransformer):
    """
    Knowledge value resolver. Will traverse graph for specified source nodes that have a connection to
    specified destination nodes, and then resolve the value property attatched to the destination node and link it
    directly to the source node. The result is that the intermediate node to get to the value of the property can
    be removed.
    The user can also provide a flag to decide if the intermediate node should be removed or not after performing
    the mapping from source node to the final property value.

        Ex. ResolveValues:

        Graph before pruning:
        node(A, rdf:type(Pump)) -(predicate("vendor"))>
                                node(B, rdf:type(TextObject)) -(predicate("value"))> Literal("CompanyX")

        Graph after resolving values between nodes rd:type(Pump) and rdf:type(Disc):

        node(A, rdf:type(Pump)) -(predicate("vendor"))> Literal("CompanyX")

    Args:
        source_node_type: RDF.type of source node
        destination_node_type: RDF.type of edge Node
        predicate_namespace: Namespace to use when resolving the predicate_namespace.value from the edge node to
                             the value
        delete_connecting_node: bool if the intermediate Node and Edge between source Node
                                and resolved value should be deleted. Default is True
    """

    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."

    def __init__(
        self,
        source_node_type: URIRef,
        destination_node_type: URIRef,
        property_value: Namespace,
        delete_connecting_node: bool = True,
    ):
        self.source_node_type = source_node_type
        self.destination_node_type = destination_node_type
        self.property_value = property_value
        self.delete_connecting_node = delete_connecting_node

    def transform(self, graph: Graph) -> None:
        source_subjects = graph.subjects(object=self.source_node_type, predicate=RDF.type)
        destination_subjects = [
            subject for subject in graph.subjects(object=self.destination_node_type, predicate=RDF.type)
        ]

        triples_to_delete: list[tuple[Node, Node, Node]] = []
        edges_to_delete: list[tuple[Node, Node, Node]] = []

        for subject in source_subjects:
            for predicate, object in graph.predicate_objects(subject=subject, unique=False):
                if object in destination_subjects:
                    if value := graph.value(subject=object, predicate=self.property_value.value):
                        # Create new connection from source subject to value
                        graph.add((subject, predicate, value))
                        triples_to_delete.append((object, RDF.type, self.destination_node_type))
                        edges_to_delete.append((subject, predicate, object))

        if self.delete_connecting_node:
            for delete_triple in triples_to_delete:
                graph.remove(triple=delete_triple)
            for edge_triple in edges_to_delete:
                graph.remove(triple=edge_triple)


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

    def __init__(
        self,
        node_prune_types: list[URIRef],
    ):
        self.node_prune_types = node_prune_types
        self._query_template = """
                SELECT ?subject
                WHERE {{
                    ?subject a <{rdf_type}> .
                    FILTER NOT EXISTS {{ ?s ?p ?subject }}
                }}
        """

    def transform(self, graph: Graph) -> None:
        for object_type in self.node_prune_types:
            free_standing_nodes = list(graph.query(self._query_template.format(rdf_type=object_type)))

            for node in free_standing_nodes:
                graph.remove(triple=(node["subject"], RDF.type, object_type))
