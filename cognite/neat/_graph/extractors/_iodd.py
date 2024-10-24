import re
import uuid
import xml.etree.ElementTree as ET
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import Literal as LiteralType
from xml.etree.ElementTree import Element

from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._graph.models import Triple
from cognite.neat._issues.errors import FileReadError, NeatValueError
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import to_camel
from cognite.neat._utils.xml_ import get_children

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")
XSI = Namespace("http://www.w3.org/2001/XMLSchema-instance/")

XSI_XML_PREFIX = "{http://www.w3.org/2001/XMLSchema-instance}"


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
        device_id: Optional user specified unique id/tag for actual equipment instance. If not provided, a randomly
        generated UUID will be used. The device_id must be WEB compliant,
        meaning that the characters /&?=: % are not allowed
    """

    device_elements_with_text_nodes: ClassVar[list[str]] = ["VendorText", "VendorUrl", "DeviceName", "DeviceFamily"]
    std_variable_elements_to_extract: ClassVar[list[str]] = ["V_SerialNumber", "V_ApplicationSpecificTag"]
    text_elements_language: LiteralType["en", "de"] = "en"

    def __init__(
        self,
        root: Element,
        namespace: Namespace | None = None,
        device_id: str | None = None,
    ):
        self.root = root
        self.namespace = namespace or DEFAULT_NAMESPACE

        if device_id and device_id != re.sub(r"[^a-zA-Z0-9-_.]", "", device_id):
            raise NeatValueError("Specified device_id is not web compliant. Please exclude characters: /&?=: %")

        self.device_id = (
            self.namespace[device_id] if device_id else self.namespace[f"Device_{str(uuid.uuid4()).replace('-', '_')}"]
        )

    @cached_property
    def _text_id_2value_mapping(self) -> dict[str, str]:
        """
        !!! note used for "Prototype Solution" !!!
        A mapping for text_id references to Text elements under ExternalTextCollection.
        The mapping can be used to find the Text element with matching id, and returns
        the value associated with the Text element.
        """
        mapping = {}
        if et_root := get_children(
            self.root, "ExternalTextCollection", ignore_namespace=True, include_nested_children=True, no_children=1
        ):
            if language_element := get_children(et_root[0], "PrimaryLanguage", ignore_namespace=True, no_children=1):
                if (
                    language_element[0].attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
                    == self.text_elements_language
                ):
                    if text_elements := get_children(
                        language_element[0], child_tag="Text", ignore_namespace=True, include_nested_children=True
                    ):
                        for element in text_elements:
                            if id := element.attrib.get("id"):
                                if value := element.attrib.get("value"):
                                    mapping[id] = value
        return mapping

    @classmethod
    def from_file(cls, filepath: Path, namespace: Namespace | None = None, device_id: str | None = None):
        if filepath.suffix != ".xml":
            raise FileReadError(filepath, "File is not XML.")
        return cls(ET.parse(filepath).getroot(), namespace, device_id)

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
                if p_id := process_data_element.attrib.get("id"):
                    device_id_str = remove_namespace_from_uri(device_id)
                    process_data_in_id = namespace[f"{device_id_str}.{p_id}"]

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

        if language_element := get_children(et_root, "PrimaryLanguage", ignore_namespace=True, no_children=1):
            if (
                language_element[0].attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
                == cls.text_elements_language
            ):
                if text_elements := get_children(
                    language_element[0], child_tag="Text", ignore_namespace=True, include_nested_children=True
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
                    device_id_str = remove_namespace_from_uri(device_id)
                    variable_id = f"{device_id_str}.{id}"

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
                    process_id_str = remove_namespace_from_uri(process_data_in_id)
                    record_id = f"{process_id_str}.{index}"
                    # Create connection from device node to time series
                    triples.append((process_data_in_id, IODD.variable, Literal(record_id, datatype=XSD["timeseries"])))

        return triples

    def extract(self) -> list[Triple]:
        """
        Extract RDF triples from IODD XML
        """
        return self._from_root2triples(self.root, self.namespace, self.device_id)

    def _variable2info(self, variable_element: Element) -> dict:
        """
        !!! note used for "Prototype Solution" !!!
        Extracts information relevant to a CDF time series type from a Variable element
        """

        variable_dict = {}

        if name := get_children(
            variable_element, child_tag="Name", ignore_namespace=True, include_nested_children=False, no_children=1
        ):
            if text_id := name[0].get("textId"):
                variable_dict["name"] = self._text_id_2value_mapping[text_id]
        if description := get_children(
            variable_element,
            child_tag="Description",
            ignore_namespace=True,
            include_nested_children=False,
            no_children=1,
        ):
            if text_id := description[0].get("textId"):
                variable_dict["description"] = self._text_id_2value_mapping[text_id]
        if data_type := get_children(
            variable_element, child_tag="Datatype", ignore_namespace=True, include_nested_children=False, no_children=1
        ):
            variable_dict["data_type"] = data_type[0].attrib[f"{XSI_XML_PREFIX}type"]

        return variable_dict

    def _process_record2info(self, record_element: Element) -> dict:
        """
        !!! note used for "Prototype Solution" !!!
        Extracts information relevant to a CDF time series type from a Record element
        """
        record_dict = {}

        if name := get_children(
            record_element, child_tag="Name", ignore_namespace=True, include_nested_children=False, no_children=1
        ):
            if text_id := name[0].get("textId"):
                record_dict["name"] = self._text_id_2value_mapping[text_id]
        if description := get_children(
            record_element, child_tag="Description", ignore_namespace=True, include_nested_children=False, no_children=1
        ):
            if text_id := description[0].get("textId"):
                record_dict["description"] = self._text_id_2value_mapping[text_id]
        if data_type := get_children(
            record_element,
            child_tag="SimpleDatatype",
            ignore_namespace=True,
            include_nested_children=False,
            no_children=1,
        ):
            record_dict["data_type"] = data_type[0].attrib[f"{XSI_XML_PREFIX}type"]
        if index := record_element.attrib.get("subindex"):
            record_dict["index"] = index

        return record_dict

    def _extract_enhanced_ts_information(self, json_file_path: Path):
        """
        Extract additional information like name, description and data type for Variables and ProcessDataIn
        record elements in the IODD. The purpose is for the result gile to be used for enhancing time series with more
        information when they are created in CDF.

        Args:
            json_file_path: file path for where to write the extracted information about all time series
                            in the IODD

        !!! note "Prototype Solution" !!!
        This is an intermediate solution while better support for adding this information directly
        into the knowledge graph for the timeseries node type is under development.
        """
        import json

        ts_ext_id2_info_map = {}

        # Variable elements (these are the descriptions of the sensors)
        if variable_elements := get_children(
            self.root, child_tag="Variable", ignore_namespace=True, include_nested_children=True
        ):
            for element in variable_elements:
                if id := element.attrib.get("id"):
                    device_id_str = remove_namespace_from_uri(self.device_id)
                    variable_id = f"{device_id_str}.{id}"
                    ts_ext_id2_info_map[variable_id] = self._variable2info(element)

        if process_data_in := get_children(
            self.root, "ProcessDataIn", ignore_namespace=True, include_nested_children=True
        ):
            for process_data_element in process_data_in:
                if p_id := process_data_element.attrib.get("id"):
                    device_id_str = remove_namespace_from_uri(self.device_id)
                    process_data_in_id = f"{device_id_str}.{p_id}"
                    if record_items := get_children(
                        process_data_element, "RecordItem", ignore_namespace=True, include_nested_children=True
                    ):
                        for record in record_items:
                            if index := record.attrib.get("subindex"):
                                process_record_id = f"{process_data_in_id}.{index}"
                                ts_ext_id2_info_map[process_record_id] = self._process_record2info(record)

        with Path.open(json_file_path, "w") as fp:
            json.dump(ts_ext_id2_info_map, fp, indent=2)
