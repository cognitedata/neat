import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.rdf_ import as_neat_compliant_uri
from cognite.neat.utils.text import to_camel
from cognite.neat.utils.xml_ import iterate_tree, remove_element_tag_namespace

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")
XSI = Namespace("http://www.w3.org/2001/XMLSchema-instance/")


class IODDExtractor(BaseExtractor):
    """
    IODD-XML extractor of RDF triples

    Each IODD sheet describes an IODD device. We want to extract triples that describes the device, and the
    sensors connected to the device.
    This data is described under the elements "DeviceIdentity" and "ProcessDataCollection".
    We can also extend the IODDExtractor to extract triples from other elements related to the device such as
    "EventCollection".

    Args:
        root: XML root element of IODD XML file.
        namespace: Optional custom namespace to use for extracted triples that define data
                    model instances. Defaults to DEFAULT_NAMESPACE.
        with_text_id_nodes: bool that configures the extractor to create nodes for the text elements as part of the
                            graph, or resolve their values immediately without these nodes (default).
    """

    def __init__(self, root: Element, namespace: Namespace | None = None, with_text_id_nodes: bool = False):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.with_text_id_nodes = with_text_id_nodes

        self.text_elements = root.find(
            ".//{*}ExternalTextCollection"
        )  # this property is used to resolve textId references

    @classmethod
    def from_file(cls, filepath: str | Path, namespace: Namespace | None = None, with_text_id_nodes: bool = False):
        return cls(ET.parse(filepath).getroot(), namespace, with_text_id_nodes)

    def _element2triples(self) -> list[Triple]:
        """Converts an element to triples."""
        triples: list[Triple] = []

        # Extract DeviceIdentity triples
        if di_root := self.root.find(".//{*}DeviceIdentity"):
            triples.extend(self._device_identity2triples(di_root))

        # Extract ProcessDataCollection triples -
        # this element holds the information about the sensors with data coming from MQTT
        if pc_root := self.root.find(".//{*}ProcessDataCollection"):
            triples.extend(self._process_data_collection2triples(pc_root))

        return triples

    def _resolve_text_id_value(self, text_id: str) -> str:
        for element in iterate_tree(self.text_elements):
            if text_id == element.attrib.get("id"):
                return element.attrib["value"]
        raise ValueError(f"Unable to resolve value for textId {text_id}")

    def _textid_elements2triples(self, di_root: Element, id: URIRef) -> list[Triple]:
        triples: set[Triple] = set()
        for element in iterate_tree(di_root):
            if "textId" in element.attrib:
                tag = to_camel(remove_element_tag_namespace(element.tag))

                text_id_str = element.attrib["textId"]
                rdf_object = Literal(self._resolve_text_id_value(text_id_str))
                triples.add((id, IODD[tag], rdf_object))

                # Create TextID node
                if self.with_text_id_nodes:
                    text_id_ = URIRef(text_id_str)
                    triples.add((text_id_, RDF.type, as_neat_compliant_uri(IODD["Text"])))
                    triples.add((text_id_, IODD.value, rdf_object))

                    # Create connection from device to textId node
                    triples.add((id, IODD[tag], text_id_))

        return list(triples)

    # TODO
    def _process_data_collection2triples(self, pc_root: Element) -> list[Triple]:
        """
        ProcessDataCollection contains both ProcessDataIn and ProcessDataOut. Here, we are interested in the elements
        that corresponds to actual sensor values that we will rececive from the MQTT connection.

        Most likely this is ProcessDataOut elements (to be verified).
        """
        triples: list[Triple] = []

        return triples

    def _device_identity2triples(self, di_root: Element) -> list[Triple]:
        """
        Properties and metadata related to the IO Device are described under the 'DeviceIdentity' element in the XML.
        This method extracts the triples related to the DeviceIdentity element and its child elements.

        """
        triples: list[Triple] = []

        # Extract element tag and namespace
        deviceId = di_root.attrib["deviceId"]
        id_ = URIRef(deviceId)

        for attribute_name, attribute_value in di_root.attrib.items():
            if attribute_name == "deviceId":
                # Create rdf type triple for IODD
                triples.append(
                    (
                        id_,
                        RDF.type,
                        as_neat_compliant_uri(IODD["IoddDevice"]),
                    )
                )
            else:
                # Collect attributes at root element
                triples.append((id_, IODD[attribute_name], Literal(attribute_value)))

        triples.extend(self._textid_elements2triples(di_root, id_))

        return triples

    def extract(self) -> list[Triple]:
        triples = []

        # Extract triples from IODD device XML
        triples.extend(self._element2triples())

        return triples
