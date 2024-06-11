import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import RDF, RDFS, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import as_neat_compliant_uri
from cognite.neat.utils.xml import get_children, iterate_tree

DEXPI = Namespace("http://sandbox.dexpi.org/rdl/")


class DexpiExtractor(BaseExtractor):
    """
    DEXPI-XML extractor of RDF triples

    Args:
        filepath: File path to DEXPI XML file.
        namespace: Optional custom namespace to use for extracted triples that define data
                    model instances. Defaults to DEFAULT_NAMESPACE.
    """

    def __init__(
        self,
        filepath: Path,
        namespace: Namespace | None = None,
    ):
        self.filepath = filepath
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.root = ET.parse(self.filepath).getroot()

    @classmethod
    def from_file(cls, file_path: str | Path, namespace: Namespace | None = None):
        return cls(Path(file_path), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extracts RDF triples from DEXPI XML file."""

        for element in iterate_tree(self.root):
            yield from self._element2triples(element, self.namespace)

    @classmethod
    def _element2triples(cls, element: Element, namespace: Namespace) -> list[Triple]:
        """Converts an element to triples."""
        triples: list[Triple] = []

        if (
            "ComponentClass" in element.attrib
            and element.attrib["ComponentClass"] != "Label"
            and "ID" in element.attrib
        ):
            id_ = namespace[element.attrib["ID"]]

            if node_triples := cls._element2node_triples(id_, element):
                triples.extend(node_triples)

            if edge_triples := cls._element2edge_triples(id_, element, namespace):
                triples.extend(edge_triples)

        return triples

    @classmethod
    def _element2edge_triples(cls, id_: URIRef, element: Element, namespace: Namespace) -> list[Triple]:
        triples: list[Triple] = []

        # connection triples
        if connections := get_children(element, "Connection"):
            for connection in connections:
                if "FromID" in connection.attrib and "ToID" in connection.attrib:
                    triples.append(
                        (
                            namespace[connection.attrib["FromID"]],
                            DEXPI.connection,
                            namespace[connection.attrib["ToID"]],
                        )
                    )

        # association triples
        if associations := get_children(element, "Association"):
            for association in associations:
                if "Type" in association.attrib and "ItemID" in association.attrib:
                    association_type = cls._to_uri_friendly_association_type(association)

                    triples.append(
                        (
                            id_,
                            DEXPI[f"association/{association_type}"],
                            namespace[association.attrib["ItemID"]],
                        )
                    )

        # children-parent triples
        for child in element:
            if "ID" in child.attrib and child.tag != "Label":
                camel_case_property = child.tag[0].lower() + child.tag[1:]
                triples.append(
                    (
                        id_,
                        DEXPI[f"children/{camel_case_property}"],
                        namespace[child.attrib["ID"]],
                    )
                )

        return triples

    @classmethod
    def _to_uri_friendly_association_type(cls, association):
        association_type = "".join(
            [word.capitalize() if i != 0 else word for i, word in enumerate(association.attrib["Type"].split(" "))]
        )

        return association_type

    @classmethod
    def _element2node_triples(cls, id_: URIRef, element: Element) -> list[Triple]:
        """Converts an XML element to triples."""
        triples: list[Triple] = []

        # adding tag triple if exists
        if tag := element.tag:
            triples.append((id_, DEXPI.tag, Literal(str(tag))))

        # adding attributes triples
        if attributes := element.attrib:
            if component_class := attributes.get("ComponentClass", None):
                triples.append((id_, DEXPI.ComponentClass, Literal(component_class)))
            if component_name := attributes.get("ComponentName", None):
                triples.append((id_, DEXPI.ComponentName, Literal(component_name)))
            if type_ := attributes.get("ComponentClassURI", None):
                triples.append((id_, RDF.type, URIRef(type_)))

        # add label triple
        if label := cls._get_element_label(element):
            triples.append((id_, RDFS.label, Literal(label)))

        # add generic attributes triples
        if generic_attributes := cls._get_element_generic_attributes(element):
            for attribute, value_definitions in generic_attributes.items():
                predicate = as_neat_compliant_uri(attribute)
                for value_definition in value_definitions:
                    if literal := cls._value_definition2literal(value_definition):
                        triples.append((id_, predicate, literal))

        return triples

    @classmethod
    def _value_definition2literal(cls, definition: dict) -> Literal | None:
        if "Value" not in definition or "Format" not in definition:
            return None

        # case: when language is present we create add language tag to the literal
        elif "Language" in definition and "Value" in definition:
            return Literal(definition["Value"], lang=definition["Language"])

        # case: when ValueURI is present we use it instead of Value
        # this would be candidate for ENUMs in CDF
        elif "ValueURI" in definition:
            return Literal(definition["ValueURI"], datatype=XSD[definition["Format"]])

        # case: when Format is not string we make sure to add the datatype
        elif definition["Format"].lower() != "string":
            return Literal(definition["Value"], datatype=XSD[definition["Format"]])

        # case: when Format is string we add the literal without datatype (easier to read triples, less noise)
        else:
            return Literal(definition["Value"])

    @classmethod
    def _get_element_label(cls, element: Element) -> str | None:
        if children := get_children(element, "Label", 1):
            if grandchildren := get_children(children[0], "Text", 1):
                if "String" in grandchildren[0].attrib:
                    return grandchildren[0].attrib["String"]

        # extension for schema version 3.3, where text is used to "label" without a <label> parent
        elif children := get_children(element, "Text", 1):
            if "String" in children[0].attrib:
                return children[0].attrib["String"]

        return None

    @classmethod
    def _get_element_generic_attributes(cls, element: Element) -> dict:
        # TODO: This requires more work as there are multiple groupings of GenericAttributes

        attributes = {}
        if children := get_children(element, "GenericAttributes", 1):
            if grandchildren := get_children(children[0], "GenericAttribute"):
                for generic_attribute in grandchildren:
                    # extension for schema version 3.3, where "AttributeURI" is not included
                    if "AttributeURI" in generic_attribute.attrib:
                        if generic_attribute.attrib["AttributeURI"] not in attributes:
                            attributes[generic_attribute.attrib["AttributeURI"]] = [generic_attribute.attrib]

                        else:
                            attributes[generic_attribute.attrib["AttributeURI"]].append(generic_attribute.attrib)

        return attributes
