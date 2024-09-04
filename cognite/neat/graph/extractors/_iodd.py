import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable
from xml.etree.ElementTree import Element

from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.rdf_ import as_neat_compliant_uri
from cognite.neat.utils.text import to_camel
from cognite.neat.utils.xml_ import iterate_tree, get_children_from_tag

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
    """

    def __init__(self, root: Element, namespace: Namespace | None = None):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE

    @classmethod
    def from_file(cls, filepath: str | Path, namespace: Namespace | None = None):
        return cls(ET.parse(filepath).getroot(), namespace)

    @classmethod
    def _element2triples(cls, root: Element, namespace: Namespace) -> list[Triple]:
        """Converts an element to triples."""
        triples: list[Triple] = []

        # Extract DeviceIdentity triples
        if di_root := root.find(".//{*}DeviceIdentity"):
            triples.extend(cls._device_identity2triples(di_root, namespace))

        # Extract ProcessDataCollection triples -
        # this element holds the information about the sensors with data coming from MQTT
        if pc_root := root.find(".//{*}ProcessDataCollection"):
            triples.extend(cls._process_data_collection2triples(pc_root, namespace))

        if et_root := root.find(".//{*}ExternalTextCollection"):
            triples.extend(cls._text_collection2triples(et_root, namespace))

        return triples

    @classmethod
    def _text_elements2edges(cls, di_root: Element, id: URIRef, namespace: Namespace) -> list[Triple]:
        """
        Create edges to elements under DeviceId that references a Text node.
        """
        triples: list[Triple] = []
        # To make it explicit what we want to extract
        child_elements = ["VendorText", "VendorUrl", "DeviceName", "DeviceFamily"]

        for child_tag in child_elements:
            if child := get_children_from_tag(di_root, child_tag=child_tag, ignore_namespace=True, no_children=1):
                if text_id := child[0].attrib.get("textId"):
                    # Create connection from device to textId node
                    tag = to_camel(child_tag)
                    triples.append((id, IODD[tag], namespace[text_id]))

        return triples

    @classmethod
    def _text_collection2triples(cls, et_root: Element, namespace: Namespace) -> list[Triple]:
        """
        This method extracts all text item triples under the ExternalTextCollection element. This will create a node
        for each text item, and add the text value as a property to the node.
        """
        triples: list[Triple] = []

        if text_elements := get_children_from_tag(et_root, child_tag="Text", ignore_namespace=True):
            for element in text_elements:
                if t_id := element.attrib.get("id"):
                    text_id = namespace[t_id]

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
    def _device_identity2triples(cls, di_root: Element, namespace: Namespace) -> list[Triple]:
        """
        Properties and metadata related to the IO Device are described under the 'DeviceIdentity' element in the XML.
        This method extracts the triples related to the DeviceIdentity element and its child elements.

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

        triples.extend(cls._text_elements2edges(di_root, id_, namespace))
        return triples

    def extract(self) -> Iterable[Triple]:
        # Extract triples from IODD device XML
        for element in iterate_tree(self.root):
            yield from self._element2triples(self.root, self.namespace)
