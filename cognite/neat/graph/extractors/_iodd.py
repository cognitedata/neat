import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar
from xml.etree.ElementTree import Element

from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.rdf_ import as_neat_compliant_uri
from cognite.neat.utils.text import to_camel
from cognite.neat.utils.xml_ import get_children_from_tag

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")
XSI = Namespace("http://www.w3.org/2001/XMLSchema-instance/")


class IODDExtractor(BaseExtractor):
    """
    IODD-XML extractor of RDF triples

    Each IODD sheet describes an IODD device. This extractor extracts rdf triples that describes the device, and the
    sensors connected to the device.
    This data is described under the elements "DeviceIdentity" and "ProcessDataCollection".
    In addition, triples extacted from "DeviceIdentity" and
    "ProcessDataCollection" may reference "Text" elements which are found under "ExternalTextCollection". Edges to
    these Text element nodes are also extracted.

    Args:
        root: XML root element of IODD XML file.
        namespace: Optional custom namespace to use for extracted triples that define data
                    model instances. Defaults to DEFAULT_NAMESPACE.
    """

    device_elements_with_text_nodes: ClassVar[list[str]] = ["VendorText", "VendorUrl", "DeviceName", "DeviceFamily"]

    def __init__(self, root: Element, namespace: Namespace | None = None):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE

    @classmethod
    def from_file(cls, filepath: str | Path, namespace: Namespace | None = None):
        return cls(ET.parse(filepath).getroot(), namespace)

    @classmethod
    def _from_root2triples(cls, root: Element, namespace: Namespace) -> list[Triple]:
        """Loops through the relevant elements of the IODD XML sheet to create rdf triples that describes the IODD
        device by starting at the root element.
        """
        triples: list[Triple] = []

        # Extract DeviceIdentity triples
        if di_root := root.find(".//{*}DeviceIdentity"):
            triples.extend(cls._iodd_device_identity2triples(di_root, namespace))

        # Extract ProcessDataCollection triples -
        # this element holds the information about the sensors with data coming from MQTT
        if pc_root := root.find(".//{*}ProcessDataCollection"):
            triples.extend(cls._process_data_collection2triples(pc_root, namespace))

        if et_root := root.find(".//{*}ExternalTextCollection"):
            triples.extend(cls._text_elements2triples(et_root, namespace))

        return triples

    @classmethod
    def _device_2text_elements_edges(cls, di_root: Element, id: URIRef, namespace: Namespace) -> list[Triple]:
        """
        Create edges from the device node to text nodes.
        """
        triples: list[Triple] = []

        for element_tag in cls.device_elements_with_text_nodes:
            if child := get_children_from_tag(di_root, child_tag=element_tag, ignore_namespace=True, no_children=1):
                if text_id := child[0].attrib.get("textId"):
                    # Create connection from device to textId node
                    element_tag = to_camel(element_tag)
                    triples.append((id, IODD[element_tag], namespace[text_id]))

        return triples

    @classmethod
    def _text_elements2triples(cls, et_root: Element, namespace: Namespace) -> list[Triple]:
        """
        This method extracts all text item triples under the ExternalTextCollection element. This will create a node
        for each text item, and add the text value as a property to the node.
        """
        triples: list[Triple] = []

        if text_elements := get_children_from_tag(et_root, child_tag="Text", ignore_namespace=True):
            for element in text_elements:
                if id := element.attrib.get("id"):
                    text_id = namespace[id]

                    # Create Text node
                    triples.append((text_id, RDF.type, as_neat_compliant_uri(IODD["Text"])))

                    # Resolve text value related to the text item
                    if value := element.attrib.get("value"):
                        triples.append((text_id, IODD.value, Literal(value)))

        return triples

    # TODO
    @classmethod
    def _process_data_collection2triples(cls, pc_root: Element, namespace: Namespace) -> list[Triple]:
        """
        ProcessDataCollection contains both ProcessDataIn and ProcessDataOut. Here, we are interested in the elements
        that corresponds to actual sensor values that we will rececive from the MQTT connection.

        Most likely this is ProcessDataOut elements (to be verified).
        """
        triples: list[Triple] = []

        return triples

    @classmethod
    def _iodd_device_identity2triples(cls, di_root: Element, namespace: Namespace) -> list[Triple]:
        """
        Properties and metadata related to the IO Device are described under the 'DeviceIdentity' element in the XML.
        This method extracts the triples that describe the device's identity which is found under the
        DeviceIdentity element and its child elements.

        """
        triples: list[Triple] = []

        id_ = namespace[di_root.attrib["deviceId"]]

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

        triples.extend(cls._device_2text_elements_edges(di_root, id_, namespace))
        return triples

    def extract(self) -> list[Triple]:
        # Extract triples from IODD device XML
        return self._from_root2triples(self.root, self.namespace)
