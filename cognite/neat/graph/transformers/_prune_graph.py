import dataclasses
from typing import Tuple

from rdflib import Graph, URIRef, RDF
from ._base import BaseTransformer


@dataclasses.dataclass
class NodeMapping:
    source_node: URIRef
    destination_node: URIRef

class ResolveValues(BaseTransformer):
    """
    Knowledge graph pruner and resolver. Will remove rdf triples from graph that does not have connections
    to other nodes, and traverse graph for specified types to resolve the value in the final node and link it to
    the source node.

        Ex. ResolveValues:

        Graph before pruning:
        node(A, rdf:type(Pump)) -(predicate("vendor"))> node(B, rdf:type(TextObject)) -(predicate("value"))> Literal("CompanyX")

        Graph after resolving values between nodes rd:type(Pump) and rdf:type(Disc):

        node(A, rdf:type(Pump)) -(predicate("vendor"))> Literal("CompanyX")

    Args:
    resolve_connection: List of mappings between source and destination node.
    """
    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."

    def __init__(
        self,
        resolve_connection: list[NodeMapping]
    ):
        self.resolve_connection = resolve_connection

    def transform(self, graph: Graph) -> None:
        ...


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
        prune_type: list of RDF types to prune from the Graph
    """
    description: str = "Prunes the graph of specified rdf types that do not have connections to other nodes."

    def __init__(
        self,
        node_prune_types: list[URIRef],
    ):

        self.node_prune_types = node_prune_types

    def transform(self, graph: Graph) -> None:

        triples_to_delete: list[Tuple] = []

        for object_type in self.node_prune_types:
            print("hei?")
            for object, predicate, subject in graph.triples(triple=(None, RDF.type, object_type)):
                # Check if Node object has an edge pointing to it from another node in the Graph, i.e object is the subject of another triple
                triple_checker = (None, None, object)
                found = False
                for _ in graph.triples(triple=triple_checker):
                    found = True
                    break
                if not found:
                    triples_to_delete.append((object, predicate, subject))

        for delete_triple in triples_to_delete:
            graph.remove(triple=delete_triple)
