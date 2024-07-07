import xml.etree.ElementTree as ET
from pathlib import Path

from rdflib import Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._dexpi import DexpiExtractor
from cognite.neat.legacy.graph.models import Triple

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
        self.namespace = Namespace(base_namespace) if isinstance(base_namespace, str | Namespace) else DEFAULT_NAMESPACE

    def extract(self) -> set[Triple]:
        """
        Extracts RDF triples from the graph capturing sheet.

        Returns:
            List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
        """
        if self.filepath is None:
            raise ValueError("File path to the graph capturing sheet is not provided!")

        root = ET.parse(self.filepath).getroot()

        # removing legacy code by reusing the maintained version of DexpiExtractor
        return set(DexpiExtractor(root, self.namespace).extract())
