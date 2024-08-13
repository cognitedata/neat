import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.rdf_ import as_neat_compliant_uri
from cognite.neat.utils.xml_ import iterate_tree, split_element_tag_namespace

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")  # All elements have this namespace as prefix
XSI = Namespace("http://www.w3.org/2001/XMLSchema-instance/")

# Not really needed or used right now as * wildcard is used to extract elements with a certain tag
ET.register_namespace("iodd", IODD.__str__())
NS = {"iodd": IODD.__str__()}


class IODDExtractor(BaseExtractor):
    """
    IODD-XML extractor of RDF triples

    Each IODD sheet describes the device identity. Goal is to extract the DeviceIdentity field along with variables (time series defs)
    for that device

    Args:
        root: XML root element of IODD XML file.
        namespace: Optional custom namespace to use for extracted triples that define data
                    model instances. Defaults to DEFAULT_NAMESPACE.
    """

    def __init__(
        self,
        root: Element,
        namespace: Namespace | None = None,
    ):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE

        # self.text_instances = root.findall(".//{*}Text")
        # self.variable_instances = root.findall(".//{*}Variable")

    @classmethod
    def from_file(cls, filepath: str | Path, namespace: Namespace | None = None):
        return cls(ET.parse(filepath).getroot(), namespace)

    @classmethod
    def _element2triples(cls, element: Element, namespace: Namespace) -> list[Triple]:
        """Converts an element to triples."""
        triples: list[Triple] = []

        # Extract DeviceIdentity triples
        if di_root := element.find(".//{*}DeviceIdentity"):
            triples.extend(cls._device_identity_to_triples(di_root, namespace))

        # Extract VariableCollection triples - this element holds the information about the sensors
        # TODO

        return triples

    @classmethod
    def _device_identity_to_triples(cls, di_root: Element, namespace: Namespace) -> list[Triple]:
        """
        Properties and metadata related to the IO Device are described under the 'DeviceIdentity' element in the XML.
        This method extracts the triples related to the DeviceIdentity element and its child elements.

        """
        triples: list[Triple] = []

        # Extract element tag and namespace
        deviceId = di_root.attrib.get("deviceId")
        id_ = namespace[deviceId]
        triples.append((id_, IODD.tag, Literal("DeviceIdentity")))

        # Create rdf type triple from DeviceIdentity
        triples.append(
            (
                id_,
                RDF.type,
                as_neat_compliant_uri(DEFAULT_NAMESPACE["DeviceIdentity"]),
            )
        )

        # add DeviceIdentity attributes triples
        for attribute_name, attribute_value in di_root.attrib.items():
            triples.append((id_, IODD[attribute_name], Literal(attribute_value)))

        # add children elements triples
        for element in di_root:
            tag, namespace = split_element_tag_namespace(element)
            if tag == "DeviceVariantCollection":
                children = iterate_tree(element, skip_root=True)
                for child in children:
                    child_tag, child_namespace = split_element_tag_namespace(child)
                    triples.append((id_, IODD.tag, Literal(child_tag)))
                    for attribute_name, attribute_value in child.attrib.items():
                        predicate = DEFAULT_NAMESPACE[f"{child_tag}/{attribute_name}"]
                        triples.append((id_, predicate, Literal(attribute_value)))
            else:
                triples.append((id_, IODD.tag, Literal(tag)))
                for attribute_name, attribute_value in element.attrib.items():
                    predicate = DEFAULT_NAMESPACE[f"{tag}/{attribute_name}"]
                    triples.append((id_, predicate, Literal(attribute_value)))

        return triples

    def extract(self) -> list[Triple]:
        triples = []

        # Extract triples from IODD device XML
        triples.extend(self._element2triples(self.root, self.namespace))

        return triples
