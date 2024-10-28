from collections.abc import Iterable
from pathlib import Path
from typing import cast

from rdflib import URIRef
from rdflib.util import guess_format

from cognite.neat._constants import DEFAULT_BASE_URI
from cognite.neat._graph._shared import rdflib_to_mime_types
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._graph.models import Triple
from cognite.neat._issues._base import IssueList
from cognite.neat._issues.errors import FileNotFoundNeatError, FileTypeUnexpectedError


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
        base_uri: URIRef = DEFAULT_BASE_URI,
        issue_list: IssueList | None = None,
    ):
        self.issue_list = issue_list or IssueList(title=f"{filepath.name}")

        self.filepath = filepath
        self.mime_type = rdflib_to_mime_types(cast(str, guess_format(str(self.filepath))))
        self.base_uri = base_uri

        if not self.filepath.exists():
            self.issue_list.append(FileNotFoundNeatError(self.filepath))

        if not self.mime_type:
            self.issue_list.append(
                FileTypeUnexpectedError(
                    self.filepath,
                    frozenset([".rdf", ".ttl", ".nt", ".n3", ".owl", ".nq", ".trig"]),
                )
            )

    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()
