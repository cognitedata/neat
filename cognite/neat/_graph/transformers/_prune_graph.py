from rdflib import Graph, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat._utils.rdf_ import as_neat_compliant_uri
from cognite.neat._utils.text import sentence_or_string_to_camel

from ._base import BaseTransformer


class TwoHopFlattener:
    """
    Transformer that will flatten the distance between a source node, an intermediate connecting node, and a
    target property that is connected to the intermediate node.
    The transformation result is that the target property is attached directly to the source node, instead of having
    to go via the intermediate node.
    There is also an option to create a new predicate for the new direct relation, if there is a property on the
    intermediate node that holds the value of the new predicate. If this parameter is not provided by the user, the
    original predicate between the source node, and the resolved target value will be used.
    The user can provide a flag to decide if the intermediate node should be removed from the graph or not
    after connecting the target property to the source node. The default here is False.

    If delete_connecting_node is not set, the expected number of triples after this transformation should be the same as
    before the transformation.
    If delete_connecting_node is set, the expected number of triples should be:
        #triples_before - #destination_nodes * #destination_nodes_properties

        Ex. TwoHopFlattener:

        Graph before transformation:
        <http://purl.org/cognite/neat/Pump-1> a ns1:Pump ;
        ns1:Attribute <http://purl.org/cognite/neat/Attribute-1234> .

        <http://purl.org/cognite/neat/Attribute-1234> a ns1:Attribute ;
        ns1:Name "ItemTagAssignmentClass" ;
        ns1:Value "D-20PSV0002" .

        Graph after transformation with args
        (destination_node_type = ns1:Attribute, namespace = ns1, value_property_name="Value",
        predicate_property_name = "Name", delete_connectiong_node=True):

        <http://purl.org/cognite/neat/Pump-1> a ns1:Pump ;
        ns1:ItemTagAssignmentClass "D-20PSV0002" .

        Number of triples after operation: 5 - 1*3 = 2

    Args:
        destination_node_type: RDF.type of edge Node
        namespace: RDF Namespace to use when querying the graph
        value_property_name: str with name of the property that holds the value attached to the intermediate node
        predicate_property_name: Optional str of the property name that holds the new predicate to use when resolving
        the intermediate connection.
        delete_connecting_node: bool if the intermediate Node and Edge between source Node
                                and target property should be deleted. Defaults to False.
    """

    description: str = "Prunes the graph of specified node types that do not have connections to other nodes."

    _query_template_keep_old_predicate: str = """
    SELECT ?sourceNode ?property_source ?destinationNode ?property_destination ?property_value WHERE {{
        ?sourceNode ?property_source ?destinationNode .
        ?destinationNode ?property_destination ?property_value .
        ?destinationNode a <{destination_node_type}> .
        ?destinationNode <{value_property_predicate}> ?property_value . }}"""

    _query_template_new_predicate: str = """
    SELECT ?sourceNode ?property ?destinationNode ?predicate_value ?property_value WHERE {{
        ?sourceNode ?property ?destinationNode .
        ?destinationNode a <{destination_node_type}> .
        ?destinationNode <{predicate_property_predicate}> ?predicate_value .
        ?destinationNode <{value_property_predicate}> ?property_value . }}"""

    def __init__(
        self,
        destination_node_type: URIRef,
        namespace: Namespace,
        value_property_name: str,
        delete_connecting_node: bool = False,
        predicate_property_name: str | None = None,
    ):
        self.destination_node_type = destination_node_type
        self.namespace = namespace
        self.value_property_predicate = self.namespace[value_property_name]
        self.delete_connecting_node = delete_connecting_node
        self.predicate_property_name = predicate_property_name

    def transform(self, graph) -> None:
        nodes_to_delete: list = []

        if self.predicate_property_name is not None:
            predicate_property_predicate = self.namespace[self.predicate_property_name]
            query = self._query_template_new_predicate.format(
                destination_node_type=self.destination_node_type,
                predicate_property_predicate=predicate_property_predicate,
                value_property_predicate=self.value_property_predicate,
            )
        else:
            query = self._query_template_keep_old_predicate.format(
                destination_node_type=self.destination_node_type,
                value_property_predicate=self.value_property_predicate,
            )

        graph_traversals = graph.query(query)

        for result_raw in graph_traversals:
            source_node, old_predicate, destination_node, new_predicate_value, new_property_value = (
                result_raw.asdict().values()
            )

            if self.predicate_property_name is not None:
                # Ensure new predicate is URI compliant as we are creating a new predicate
                new_predicate_value_string = sentence_or_string_to_camel(str(new_predicate_value))
                predicate = as_neat_compliant_uri(self.namespace[new_predicate_value_string])
            else:
                predicate = old_predicate

            # Create new connection from source node to value
            graph.add((source_node, predicate, new_property_value))
            # Remove old relationship between source node and destination node
            graph.remove((source_node, predicate, destination_node))

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
                    graph.remove((node["subject"], None, None))
