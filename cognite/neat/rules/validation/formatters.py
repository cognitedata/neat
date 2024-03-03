import warnings
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path

from ._base import Error, IssueList, ValidationWarning


class Formatter(ABC):
    file_suffix: str

    @abstractmethod
    def create_report(self, issues: IssueList) -> str:
        raise NotImplementedError()

    def write_to_file(self, issues: IssueList, file_path: Path) -> None:
        if file_path.suffix != self.file_suffix:
            warnings.warn(
                f"File suffix is not {self.file_suffix}. Appending suffix to file path.", UserWarning, stacklevel=2
            )
            file_path = file_path.with_suffix(self.file_suffix)
        file_path.write_text(self.create_report(issues))


class BasicHTMLFormatter(Formatter):
    file_suffix = ".html"

    def __init__(self):
        self._doc = ET.Element("html")
        self._body = ET.SubElement(self._doc, "body")

    def create_report(self, issues: IssueList) -> str:
        errors = [issue for issue in issues if isinstance(issue, Error)]
        warnings_ = [issue for issue in issues if isinstance(issue, ValidationWarning)]
        self._doc.clear()
        self._body = ET.SubElement(self._doc, "body")
        h1 = ET.SubElement(self._body, "h1")
        h1.text = f"Validation Report: {issues.title or 'Missing title'}"

        if errors:
            h2 = ET.SubElement(self._body, "h2")
            h2.text = "Errors"
            self._write_errors_or_warnings(errors)

        if warnings_:
            h2 = ET.SubElement(self._body, "h2")
            h2.text = "Warnings"
            self._write_errors_or_warnings(warnings_)

        return ET.tostring(self._doc, encoding="unicode")

    def _write_errors_or_warnings(self, issues: list[Error] | list[ValidationWarning]) -> None:
        ...
