from collections.abc import Iterable
from pathlib import Path


import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element

from rdflib import OWL, RDF, RDFS, SKOS, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE

from cognite.neat.utils.utils import get_namespace, remove_namespace
from cognite.neat.utils.xml import get_children, iterate_tree

from cognite.neat.rules.models.entities import _ALLOWED_PATTERN

from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple


_DEXPI_PREFIXES = {
    "dexpi": Namespace("http://sandbox.dexpi.org/rdl/"),
    "posccaesar": Namespace("http://data.posccaesar.org/rdl/"),
}


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
        file_path: Path,
        namespace: Namespace | None = None,
    ):
        self.file_path = file_path
        self.namespace = namespace or DEFAULT_NAMESPACE

        self.root = ET.parse(self.file_path).getroot()

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

            node_triples = cls._element2node_triples(id_, element, namespace)
