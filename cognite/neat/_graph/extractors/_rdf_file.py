import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import cast, get_args

from rdflib import URIRef
from rdflib.util import guess_format

from cognite.neat._constants import DEFAULT_BASE_URI
from cognite.neat._graph._shared import RDFTypes
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._issues._base import IssueList
from cognite.neat._issues.errors import FileNotFoundNeatError, FileTypeUnexpectedError
from cognite.neat._issues.errors._general import NeatValueError
from cognite.neat._shared import Triple


class RdfFileExtractor(BaseExtractor):
    """Extract data from RDF files into Neat.

    Args:
        filepath (Path): The path to the RDF file.
        mime_type (MIMETypes, optional): The MIME type of the RDF file. Defaults to "application/rdf+xml".
        base_uri (URIRef, optional): The base URI to use. Defaults to None.
    """

    def __init__(
        self,
        filepath: Path | zipfile.ZipExtFile,
        base_uri: URIRef = DEFAULT_BASE_URI,
        issue_list: IssueList | None = None,
    ):
        self.issue_list = issue_list or IssueList(title=f"{filepath.name}")
        self.base_uri = base_uri
        self.filepath = filepath

        self.format = guess_format(str(self.filepath) if isinstance(self.filepath, Path) else self.filepath.name)

        if isinstance(self.filepath, Path) and not self.filepath.exists():
            self.issue_list.append(FileNotFoundNeatError(self.filepath))

        if not self.format:
            self.issue_list.append(
                FileTypeUnexpectedError(
                    (self.filepath if isinstance(self.filepath, Path) else Path(self.filepath.name)),
                    frozenset(get_args(RDFTypes)),
                )
            )

    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()

    @classmethod
    def from_zip(
        cls,
        filepath: Path,
        filename: str = "neat-session/instances/instances.trig",
        base_uri: URIRef = DEFAULT_BASE_URI,
        issue_list: IssueList | None = None,
    ):
        if not filepath.exists():
            raise FileNotFoundNeatError(filepath)
        if filepath.suffix not in {".zip"}:
            raise NeatValueError("Expected a zip file, got {filepath.suffix}")

        with zipfile.ZipFile(filepath, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename == filename:
                    # We need to open the file in the zip file, and close it upon
                    # triple extraction ...

                    print(file_info)
                    file = zip_ref.open(file_info)
                    return cls(cast(zipfile.ZipExtFile, file), base_uri, issue_list)

        raise NeatValueError(f"Cannot extract {filename} from zip file {filepath}")
