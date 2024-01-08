import re
import xml.etree.ElementTree as ET
from collections.abc import Generator
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import OWL, RDF, RDFS, SKOS, XSD, Literal, Namespace, URIRef

from cognite.neat.graph.models import Triple
from cognite.neat.rules.models._base import ALLOWED_PATTERN
from cognite.neat.utils.utils import get_namespace, remove_namespace

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
        self.namespace = (
            Namespace(base_namespace)
            if isinstance(base_namespace, str | Namespace)
            else Namespace("http://purl.org/cognite/neat/")
        )

    def extract(self) -> set[Triple]:
        """
        Extracts RDF triples from the graph capturing sheet.

        Returns:
            List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
        """
        if self.filepath is None:
            raise ValueError("File path to the graph capturing sheet is not provided!")

        root = ET.parse(self.filepath).getroot()

        nodes, edges = extract_nodes_and_edges(root)

        return to_triples(nodes, edges, base_namespace=self.namespace)


def iterate_tree(node: Element) -> Generator:
    """Iterate over all elements in an XML tree.

    Args:
        node: XML tree to iterate over.

    Returns:
        Generator of XML elements.
    """
    yield node
    for child in node:
        yield from iterate_tree(child)


def get_children(element: Element, child_tag: str, no_children: int = -1) -> list[Element]:
    """Get children of an XML element.

    Args:
        element: XML element to get children from.
        child_tag: Tag of the children to get.
        no_children: Max number of children to get. Defaults to -1 (all).

    Returns:
        List of XML elements if no_children > 1, otherwise XML element.
    """
    children = []
    for child in element:
        if child.tag == child_tag:
            if no_children == 1:
                return [child]
            else:
                children.append(child)
    return children


def extract_nodes_and_edges(root: Element) -> tuple[dict, dict]:
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
            # add header that contains things such as type
            nodes[element.attrib["ID"]] = {"header": element.attrib}
            nodes[element.attrib["ID"]]["header"]["tag"] = str(element.tag)

            # add generic attributes
            if gen_atribute := get_children(element, "GenericAttributes", 1):
                if grandchildren := get_children(gen_atribute[0], "GenericAttribute"):
                    for grandchild in grandchildren:
                        if grandchild.attrib["AttributeURI"] not in nodes[element.attrib["ID"]]:
                            nodes[element.attrib["ID"]][grandchild.attrib["AttributeURI"]] = [grandchild.attrib]
                        else:
                            nodes[element.attrib["ID"]][grandchild.attrib["AttributeURI"]].append(grandchild.attrib)

            # add label which is in Label part of the xml
            if label_element := get_children(element, "Label", 1):
                if text_element := get_children(label_element[0], "Text", 1):
                    if "String" in text_element[0].attrib:
                        nodes[element.attrib["ID"]]["header"]["label"] = text_element[0].attrib["String"]

            # edges scenario: <Connection> tag
            if connections := get_children(element, "Connection"):
                for connection in connections:
                    if "FromID" in connection.attrib and "ToID" in connection.attrib:
                        edges["connections"].add((connection.attrib["FromID"], "connection", connection.attrib["ToID"]))

            # edges scenario: <Association> tag
            if associations := get_children(element, "Association"):
                for association in associations:
                    if "Type" in association.attrib and "ItemID" in association.attrib:
                        association_type = "".join(
                            [
                                word.capitalize() if i != 0 else word
                                for i, word in enumerate(association.attrib["Type"].split(" "))
                            ]
                        )
                        edges["associations"].add(
                            (element.attrib["ID"], f"{association_type}", association.attrib["ItemID"])
                        )

            # edge scenario: children elements of the element
            for child in element:
                if "ID" in child.attrib and child.tag != "Label":
                    edges["children"].add((element.attrib["ID"], child.tag, child.attrib["ID"]))
    return nodes, edges


def get_datatype_triples(base_namespace: Namespace, unit_definition: dict):
    return {
        (base_namespace[unit_definition["Units"]], RDF.type, RDFS.Datatype),
        (base_namespace[unit_definition["Units"]], RDFS.label, Literal(unit_definition["Units"])),
        (base_namespace[unit_definition["Units"]], OWL.equivalentClass, XSD[unit_definition["Format"]]),
        (base_namespace[unit_definition["Units"]], SKOS.exactMatch, URIRef(unit_definition["UnitsURI"])),
    }


def to_triples(nodes: dict, edges: dict, base_namespace: Namespace) -> set[Triple]:
    """Convert nodes and edges to triples.

    Args:
        nodes: Nodes to convert to triples.
        edges: Edges to convert to triples.

    Returns:
        List of triples.
    """
    triples: set[Triple] = set()

    # Adding nodes and nodes attributes
    for node_id, node_attributes in nodes.items():
        node_uri = URIRef(base_namespace + node_id)

        triples.add((node_uri, RDF.type, URIRef(node_attributes["header"]["ComponentClassURI"])))
        triples.add((node_uri, _DEXPI_PREFIXES["dexpi"].tag, Literal(node_attributes["header"]["tag"])))

        if "ComponentClass" in node_attributes["header"]:
            triples.add(
                (
                    node_uri,
                    _DEXPI_PREFIXES["dexpi"].ComponentClass,
                    Literal(node_attributes["header"]["ComponentClass"]),
                )
            )

        if "ComponentName" in node_attributes["header"]:
            triples.add(
                (node_uri, _DEXPI_PREFIXES["dexpi"].ComponentName, Literal(node_attributes["header"]["ComponentName"]))
            )

        if "label" in node_attributes["header"]:
            triples.add((node_uri, RDFS.label, Literal(node_attributes["header"]["label"])))

        for attribute, values in node_attributes.items():
            if attribute != "header":
                # attribute contains illegal characters

                namespace = get_namespace(attribute)
                attribute_name = remove_namespace(attribute)
                compliant_attribute_name = re.sub(ALLOWED_PATTERN, "", attribute_name)

                if attribute_name != compliant_attribute_name:
                    attribute = f"{namespace}{compliant_attribute_name}"
                    triples.add(
                        (
                            URIRef(attribute),
                            SKOS.exactMatch,
                            URIRef(f"{namespace}{attribute_name}"),
                        )
                    )
                    triples.add(
                        (
                            URIRef(attribute),
                            SKOS.comment,
                            Literal("Modified property URI to be compliant with NEAT internal representation"),
                        )
                    )

                for value in values:
                    if "Value" not in value or "Format" not in value:
                        continue
                    if "Units" in value:
                        triples.update(get_datatype_triples(_DEXPI_PREFIXES["dexpi"], value))
                        triples.add(
                            (
                                node_uri,
                                URIRef(attribute),
                                Literal(value["Value"], datatype=_DEXPI_PREFIXES["dexpi"][value["Units"]]),
                            )
                        )

                    elif "Language" in value and "Value" in value:
                        triples.add((node_uri, URIRef(attribute), Literal(value["Value"], lang=value["Language"])))
                    elif "ValueURI" in value:
                        triples.add(
                            (node_uri, URIRef(attribute), Literal(value["ValueURI"], datatype=XSD[value["Format"]]))
                        )
                    elif value["Format"].lower() != "string":
                        triples.add(
                            (node_uri, URIRef(attribute), Literal(value["Value"], datatype=XSD[value["Format"]]))
                        )
                    else:
                        triples.add((node_uri, URIRef(attribute), Literal(value["Value"])))

    # Adding Edges: type connections
    for subject, predicate, object in edges["connections"]:
        triples.add(
            (URIRef(base_namespace + subject), _DEXPI_PREFIXES["dexpi"][predicate], URIRef(base_namespace + object))
        )

    # Adding Edges: type associations
    for subject, predicate, object in edges["associations"]:
        triples.add(
            (
                URIRef(base_namespace + subject),
                _DEXPI_PREFIXES["dexpi"][f"association/{predicate}"],
                URIRef(base_namespace + object),
            )
        )
    # Adding Edges: type children
    for subject, predicate, object in edges["children"]:
        triples.add(
            (
                URIRef(base_namespace + subject),
                _DEXPI_PREFIXES["dexpi"][f"children/has{predicate}"],
                URIRef(base_namespace + object),
            )
        )

    return triples
