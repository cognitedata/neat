import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import OWL, RDF, RDFS, SKOS, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.graph.models import Triple
from cognite.neat.rules.models._base import ALLOWED_PATTERN
from cognite.neat.utils.utils import get_namespace, remove_namespace
from cognite.neat.utils.xml import get_children, iterate_tree

from ._base import BaseExtractor

_DEXPI_PREFIXES = {
    "dexpi": Namespace("http://sandbox.dexpi.org/rdl/"),
    "posccaesar": Namespace("http://data.posccaesar.org/rdl/"),
}


class DexpiXML(BaseExtractor):
    """
    DEXPI-XML extractor of RDF triples

    Args:
        filepath: File path to DEXPI XML file.
        namespace: Optional custom namespace to use for extracted triples that define data
                    model instances. Defaults to http://purl.org/cognite/neat/.
    """

    def __init__(
        self,
        filepath: Path | str,
        base_namespace: str | None = None,
    ):
        self.filepath = Path(filepath)
        self.namespace = Namespace(base_namespace) if isinstance(base_namespace, str | Namespace) else PREFIXES["neat"]

    def extract(self) -> set[Triple]:
        """
        Extracts RDF triples from the graph capturing sheet.

        Returns:
            List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
        """
        if self.filepath is None:
            raise ValueError("File path to the graph capturing sheet is not provided!")

        root = ET.parse(self.filepath).getroot()

        nodes, edges = _extract_nodes_and_edges(root)

        self.nodes = nodes

        return _to_triples(nodes, edges, base_namespace=self.namespace)


def _extract_nodes_and_edges(root: Element) -> tuple[dict, dict]:
    """Extract nodes and edges from an XML tree.

    Args:
        root: XML tree to extract nodes and edges from.

    Returns:
        Tuple of nodes and edges.
    """
    nodes: dict = {}
    edges: dict = {"associations": set(), "connections": set(), "children": set()}

    for element in iterate_tree(root):
        if (
            "ComponentClass" in element.attrib
            and element.attrib["ComponentClass"] != "Label"
            and "ID" in element.attrib
        ):
            id_ = element.attrib["ID"]

            # add header that contains things such as type
            nodes[id_] = {"header": element.attrib, "attributes": {}}
            nodes[id_]["header"]["tag"] = str(element.tag)

            # add human readable label of node (if exists)
            nodes = _add_node_label(id_, nodes, element)

            # add generic attributes of node
            nodes = _add_node_generic_attributes(id_, nodes, element)

            # edges scenario: <Connection> tag
            edges = _add_connection_edge(edges, element)

            # edges scenario: <Association> tag
            edges = _add_association_edge(id_, edges, element)

            # edge scenario: children elements of the element
            edges = _add_child_edge(id_, edges, element)

    return nodes, edges


def _add_node_label(id_: str, nodes: dict, element: Element) -> dict:
    if children := get_children(element, "Label", 1):
        if grandchildren := get_children(children[0], "Text", 1):
            if "String" in grandchildren[0].attrib:
                nodes[id_]["header"]["label"] = grandchildren[0].attrib["String"]

    return nodes


def _add_node_generic_attributes(id_: str, nodes: dict, element: Element) -> dict:
    if children := get_children(element, "GenericAttributes", 1):
        if grandchildren := get_children(children[0], "GenericAttribute"):
            for generic_attribute in grandchildren:
                if generic_attribute.attrib["AttributeURI"] not in nodes[id_]:
                    nodes[id_]["attributes"][generic_attribute.attrib["AttributeURI"]] = [generic_attribute.attrib]
                else:
                    nodes[id_]["attributes"][generic_attribute.attrib["AttributeURI"]].append(generic_attribute.attrib)

    return nodes


def _add_connection_edge(edges: dict, element: Element) -> dict:
    if "connections" not in edges:
        edges["connections"] = set()

    if connections := get_children(element, "Connection"):
        for connection in connections:
            if "FromID" in connection.attrib and "ToID" in connection.attrib:
                edges["connections"].add((connection.attrib["FromID"], "connection", connection.attrib["ToID"]))

    return edges


def _add_association_edge(id_: str, edges: dict, element: Element) -> dict:
    if "associations" not in edges:
        edges["associations"] = set()

    if associations := get_children(element, "Association"):
        for association in associations:
            if "Type" in association.attrib and "ItemID" in association.attrib:
                association_type = "".join(
                    [
                        word.capitalize() if i != 0 else word
                        for i, word in enumerate(association.attrib["Type"].split(" "))
                    ]
                )
                edges["associations"].add((id_, f"{association_type}", association.attrib["ItemID"]))

    return edges


def _add_child_edge(id_: str, edges: dict, element: Element) -> dict:
    if "children" not in edges:
        edges["children"] = set()

    for child in element:
        if "ID" in child.attrib and child.tag != "Label":
            edges["children"].add((id_, child.tag, child.attrib["ID"]))

    return edges


def _to_triples(nodes: dict, edges: dict, base_namespace: Namespace) -> set[Triple]:
    """Convert nodes and edges to subject-predicate-object triples.

    Args:
        nodes: Nodes to convert to triples.
        edges: Edges to convert to triples.

    Returns:
        List of triples.
    """
    triples: set[Triple] = set()

    # Adding nodes and nodes attributes
    for id_, node in nodes.items():
        uri = URIRef(base_namespace + id_)

        # add header attribute triples
        triples = _add_header_triples(uri, triples, node["header"], "ComponentClassURI", RDF.type)
        triples = _add_header_triples(uri, triples, node["header"], "label", RDFS.label)
        triples = _add_header_triples(uri, triples, node["header"], "tag")
        triples = _add_header_triples(uri, triples, node["header"], "ComponentClass")
        triples = _add_header_triples(uri, triples, node["header"], "ComponentName")

        # add generic attribute triples
        for attribute, values in node["attributes"].items():
            attribute_uri, triples = _to_compliant_attribute_uri(URIRef(attribute), triples)

            for value in values:
                triples = _add_attribute_triples(uri, triples, attribute_uri, value)

    # Adding Edges
    triples = _add_edge_triples(edges["connections"], triples, "connections", base_namespace)
    triples = _add_edge_triples(edges["associations"], triples, "associations", base_namespace)
    triples = _add_edge_triples(edges["children"], triples, "children", base_namespace)

    return triples


def _add_edge_triples(
    edges: set[tuple[str, str, str]], triples: set[Triple], edge_type: str, base_namespace: Namespace
) -> set[Triple]:
    """Convert edges to subject-predicate-object triples.

    Args:
        edges: Edges to convert to triples.

    Returns:
        List of triples.
    """

    for subject, predicate, object in edges:
        if edge_type != "connections":
            predicate_uri = _DEXPI_PREFIXES["dexpi"][f"{edge_type}/{predicate}"]
        else:
            predicate_uri = _DEXPI_PREFIXES["dexpi"][predicate]

        triples.add((URIRef(base_namespace + subject), predicate_uri, URIRef(base_namespace + object)))

    return triples


def _add_header_triples(
    uri: URIRef, triples: set[Triple], attributes: dict, attribute: str, attribute_uri: URIRef | None = None
) -> set[Triple]:
    if attribute not in attributes:
        return triples

    attribute_uri = attribute_uri or _DEXPI_PREFIXES["dexpi"][attribute]

    if attribute in attributes and attribute_uri == RDF.type:
        triples.add((uri, attribute_uri, URIRef(attributes[attribute])))
    else:
        triples.add((uri, attribute_uri, Literal(attributes[attribute])))

    return triples


def _to_compliant_attribute_uri(attribute_uri: URIRef, triples: set[Triple]) -> tuple[URIRef, set[Triple]]:
    namespace = get_namespace(attribute_uri)
    id_ = remove_namespace(attribute_uri)
    compliant_id = re.sub(ALLOWED_PATTERN, "", id_)
    compliant_attribute_uri = URIRef(f"{namespace}{compliant_id}")

    if attribute_uri != compliant_attribute_uri:
        triples.add(
            (
                compliant_attribute_uri,
                SKOS.exactMatch,
                attribute_uri,
            )
        )
        triples.add(
            (
                compliant_attribute_uri,
                RDFS.comment,
                Literal("Modified property URI to be compliant with NEAT internal representation"),
            )
        )

    return compliant_attribute_uri, triples


def _add_attribute_triples(uri: URIRef, triples: set[Triple], attribute_uri, value: dict) -> set[Triple]:
    # case: when Value or Format is not present we skip the attribute since it is not formatted correctly
    if "Value" not in value or "Format" not in value:
        return triples

    # case: when unit is present we create a special datatype for it
    if "Units" in value:
        triples.update(_generate_datatype_triples(_DEXPI_PREFIXES["dexpi"], value))
        triples.add(
            (
                uri,
                attribute_uri,
                Literal(value["Value"], datatype=_DEXPI_PREFIXES["dexpi"][value["Units"]]),
            )
        )

    # case: when language is present we create add language tag to the literal
    elif "Language" in value and "Value" in value:
        triples.add((uri, attribute_uri, Literal(value["Value"], lang=value["Language"])))

    # case: when ValueURI is present we use it instead of Value
    elif "ValueURI" in value:
        triples.add((uri, attribute_uri, Literal(value["ValueURI"], datatype=XSD[value["Format"]])))

    # case: when Format is not string we make sure to add the datatype
    elif value["Format"].lower() != "string":
        triples.add((uri, attribute_uri, Literal(value["Value"], datatype=XSD[value["Format"]])))

    # case: when Format is string we add the literal without datatype (easier to read triples, less noise)
    else:
        triples.add((uri, attribute_uri, Literal(value["Value"])))

    return triples


def _generate_datatype_triples(base_namespace: Namespace, unit_definition: dict) -> set[Triple]:
    return {
        (base_namespace[unit_definition["Units"]], RDF.type, RDFS.Datatype),
        (base_namespace[unit_definition["Units"]], RDFS.label, Literal(unit_definition["Units"])),
        (base_namespace[unit_definition["Units"]], OWL.equivalentClass, XSD[unit_definition["Format"]]),
        (base_namespace[unit_definition["Units"]], SKOS.exactMatch, URIRef(unit_definition["UnitsURI"])),
    }
