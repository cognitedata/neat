import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar
from xml.etree.ElementTree import Element

from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.issues.errors import FileReadError
from cognite.neat.utils.text import to_camel
from cognite.neat.utils.xml_ import get_children

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
        device_tag: Optional user specified unique tag for actual equipment instance. If not provided, a randomly
        generated UUID will be used.
    """

    device_elements_with_text_nodes: ClassVar[list[str]] = ["VendorText", "VendorUrl", "DeviceName", "DeviceFamily"]
    std_variable_elements_to_extract: ClassVar[list[str]] = ["V_SerialNumber", "V_ApplicationSpecificTag"]

    def __init__(self, root: Element, namespace: Namespace | None = None, device_tag: str | None = None):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE

        self.device_id = (
            self.namespace[device_tag]
            if device_tag
            else self.namespace[f"Device_{str(uuid.uuid4()).replace('-', '_')}"]
        )

    @classmethod
    def from_file(cls, filepath: Path, namespace: Namespace | None = None, device_tag: str | None = None):
        if filepath.suffix != ".xml":
            raise FileReadError(filepath, "File is not XML.")
        return cls(ET.parse(filepath).getroot(), namespace, device_tag)

    @classmethod
    def _from_root2triples(cls, root: Element, namespace: Namespace, device_id: URIRef) -> list[Triple]:
        """Loops through the relevant elements of the IODD XML sheet to create rdf triples that describes the IODD
        device by starting at the root element.
        """
        triples: list[Triple] = []

        # Extract DeviceIdentity triples
        if di_root := get_children(
            root, "DeviceIdentity", ignore_namespace=True, include_nested_children=True, no_children=1
        ):
            triples.extend(cls._iodd_device_identity2triples(di_root[0], namespace, device_id))

        # Extract VariableCollection triples -
        # this element holds the information about the sensors connected to the device that collects data such as
        # temperature, voltage, leakage etc.
        if vc_root := get_children(
            root, "VariableCollection", ignore_namespace=True, include_nested_children=True, no_children=1
        ):
            triples.extend(cls._variables_data_collection2triples(vc_root[0], namespace, device_id))

        if pc_root := get_children(
            root, "ProcessDataCollection", ignore_namespace=True, include_nested_children=True, no_children=1
        ):
            triples.extend(cls._process_data_collection2triples(pc_root[0], namespace, device_id))

        if et_root := get_children(
            root, "ExternalTextCollection", ignore_namespace=True, include_nested_children=True, no_children=1
        ):
            triples.extend(cls._text_elements2triples(et_root[0], namespace))

        return triples

    @classmethod
    def _process_data_collection2triples(
        cls, pc_root: Element, namespace: Namespace, device_id: URIRef
    ) -> list[Triple]:
        """
        Will only collect ProcessDataIn elements at this point. The data from the IO-master is transmitted as an
        array related to a ProcessDataIn item.
        """
        triples: list[Triple] = []

        if process_data_in := get_children(
            pc_root, "ProcessDataIn", ignore_namespace=True, include_nested_children=True
        ):
            for process_data_element in process_data_in:
                if id := process_data_element.attrib.get("id"):
                    process_data_in_id = namespace[f"{device_id!s}_{id}"]

                    # Create ProcessDataIn node
                    triples.append((process_data_in_id, RDF.type, IODD.ProcessDataIn))

                    # Create connection from device to node
                    triples.append((device_id, IODD.processDataIn, process_data_in_id))

                    # Connect record items (essentially an array of indexed variables) to the ProcessDataIn node
                    triples.extend(cls._process_data_in_records2triples(process_data_element, process_data_in_id))

        return triples

    @classmethod
    def _device_2text_elements_edges(cls, di_root: Element, id: URIRef, namespace: Namespace) -> list[Triple]:
        """
        Create edges from the device node to text nodes.
        """
        triples: list[Triple] = []

        for element_tag in cls.device_elements_with_text_nodes:
            if child := get_children(
                di_root, child_tag=element_tag, ignore_namespace=True, include_nested_children=True, no_children=1
            ):
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

        if text_elements := get_children(
            et_root, child_tag="Text", ignore_namespace=True, include_nested_children=True
        ):
            for element in text_elements:
                if id := element.attrib.get("id"):
                    text_id = namespace[id]

                    # Create Text node
                    triples.append((text_id, RDF.type, IODD.TextObject))

                    # Resolve text value related to the text item
                    if value := element.attrib.get("value"):
                        triples.append((text_id, IODD.value, Literal(value)))

        return triples

    @classmethod
    def _std_variables2triples(cls, vc_root: Element, namespace: Namespace, device_id: URIRef) -> list[Triple]:
        """
        For simplicity, only extract the two items we want for this use case - V_ApplicationSpecificTag and
        V_SerialNumber
        """
        triples: list[Triple] = []

        if std_variable_elements := get_children(vc_root, child_tag="StdVariableRef", ignore_namespace=True):
            for element in std_variable_elements:
                if id := element.attrib.get("id"):
                    if id in cls.std_variable_elements_to_extract:
                        if object := element.attrib.get("defaultValue"):
                            predicate = to_camel(id.replace("V_", ""))
                            triples.append((device_id, IODD[predicate], Literal(object)))
        return triples

    @classmethod
    def _variables_data_collection2triples(
        cls, vc_root: Element, namespace: Namespace, device_id: URIRef
    ) -> list[Triple]:
        """
        VariableCollection contains elements that references Variables and StdVariables. The StdVariables
        can be resolved by looking up the ID in the IODD-StandardDefinitions1.1.xml sheet.

        The Variable elements are descriptions of the sensors collecting data for the device.
        """
        triples: list[Triple] = []

        # StdVariableRef elements of interest
        triples.extend(cls._std_variables2triples(vc_root, namespace, device_id))

        # Variable elements (these are the descriptions of the sensors)
        if variable_elements := get_children(vc_root, child_tag="Variable", ignore_namespace=True):
            for element in variable_elements:
                if id := element.attrib.get("id"):
                    variable_id = f"{device_id}_{id}"

                    # Create connection from device node to time series
                    triples.append((device_id, IODD.variable, Literal(variable_id, datatype=XSD["timeseries"])))

        return triples

    @classmethod
    def _iodd_device_identity2triples(cls, di_root: Element, namespace: Namespace, device_id: URIRef) -> list[Triple]:
        """
        Properties and metadata related to the IO Device are described under the 'DeviceIdentity' element in the XML.
        This method extracts the triples that describe the device's identity which is found under the
        DeviceIdentity element and its child elements.

        """
        triples: list[Triple] = []

        # Create rdf type triple for IODD
        triples.append(
            (
                device_id,
                RDF.type,
                IODD.IoddDevice,
            )
        )

        for attribute_name, attribute_value in di_root.attrib.items():
            triples.append((device_id, IODD[attribute_name], Literal(attribute_value)))

        triples.extend(cls._device_2text_elements_edges(di_root, device_id, namespace))
        return triples

    @classmethod
    def _process_data_in_records2triples(cls, pc_in_root: Element, process_data_in_id: URIRef):
        """
        Extract RecordItems related to a ProcessDataIn element. Each record item is indexed. Will use this index
        as the identifier for the time series in CDF.
        """
        triples: list[Triple] = []

        if record_items := get_children(pc_in_root, "RecordItem", ignore_namespace=True, include_nested_children=True):
            for record in record_items:
                if index := record.attrib.get("subindex"):
                    record_id = f"{process_data_in_id!s}_{index}"
                    # Create connection from device node to time series
                    triples.append((process_data_in_id, IODD.variable, Literal(record_id, datatype=XSD["timeseries"])))

        return triples

    def extract(self) -> list[Triple]:
        """
        Extract RDF triples from IODD XML
        """
        return self._from_root2triples(self.root, self.namespace, self.device_id)
