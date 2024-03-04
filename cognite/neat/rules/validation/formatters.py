import warnings
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path

from ._base import Error, IssueList, ValidationWarning

__all__ = ["Formatter", "BasicHTML", "FORMATTER_BY_NAME"]


class Formatter(ABC):
    file_suffix: str
    default_file_prefix: str = "validation_report"

    @abstractmethod
    def create_report(self, issues: IssueList) -> str:
        raise NotImplementedError()

    @property
    def default_file_name(self) -> str:
        return f"{self.default_file_prefix}_{type(self).__name__.lower()}{self.file_suffix}"

    def write_to_file(self, issues: IssueList, file_or_dir_path: Path | None = None) -> None:
        if file_or_dir_path is None:
            file_or_dir_path = Path(self.default_file_name)
        elif file_or_dir_path.is_dir():
            file_or_dir_path = file_or_dir_path / self.default_file_name

        if file_or_dir_path.suffix != self.file_suffix:
            warnings.warn(
                f"File suffix is not {self.file_suffix}. Appending suffix to file path.", UserWarning, stacklevel=2
            )
            file_or_dir_path = file_or_dir_path.with_suffix(self.file_suffix)
        file_or_dir_path.write_text(self.create_report(issues))


class BasicHTML(Formatter):
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
        issue_name = "errors" if isinstance(issues[0], Error) else "warnings"
        main_categories = {base_ for issue in issues for base_ in type(issue).__bases__}

        for category in main_categories:
            issues_in_category: list[Error] | list[ValidationWarning] = [  # type: ignore[assignment]
                issue for issue in issues if isinstance(issue, category)
            ]
            h3 = ET.SubElement(self._body, "h3")
            h3.text = category.__name__
            p = ET.SubElement(self._body, "p")
            p.text = f"Total: {len(issues_in_category)} {issue_name}"
            ul = ET.SubElement(self._body, "ul")
            for issue in issues_in_category:
                li = ET.SubElement(ul, "li")
                li.text = issue.message()


FORMATTER_BY_NAME: dict[str, type[Formatter]] = {
    subclass.__name__: subclass for subclass in Formatter.__subclasses__() if ABC not in subclass.__bases__  # type: ignore[type-abstract]
}
