from pathlib import Path

from rdflib import URIRef

from cognite.neat.graph._shared import MIMETypes
from cognite.neat.graph.extractors._base import BaseExtractor


class RdfFileExtractor(BaseExtractor):
    """Extract data from RDF files into Neat.

    Args:
        filepath (Path): The path to the RDF file.
        mime_type (MIMETypes, optional): The MIME type of the RDF file. Defaults to "application/rdf+xml".
        base_uri (URIRef, optional): The base URI to use. Defaults to None.
    """

    def __init__(
        self,
        filepath: Path,
        mime_type: MIMETypes = "application/rdf+xml",
        base_uri: URIRef | None = None,
    ):
        self.filepath = filepath
        self.mime_type = mime_type
        self.base_uri = base_uri
