from pathlib import Path

from rdflib import URIRef

from cognite.neat.graph._shared import MIMETypes
from cognite.neat.graph.extractors._base import BaseExtractor


class RdfFileExtractor(BaseExtractor):
    def __init__(
        self,
        filepath: Path,
        mime_type: MIMETypes = "application/rdf+xml",
        base_uri: URIRef | None = None,
    ):
        self.filepath = filepath
        self.mime_type = mime_type
        self.base_uri = base_uri
