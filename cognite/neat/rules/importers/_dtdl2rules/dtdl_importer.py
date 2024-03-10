import json
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, overload

from pydantic import ValidationError

from cognite.neat.rules import validation
from cognite.neat.rules._shared import Rules
from cognite.neat.rules.importers._base import BaseImporter, _handle_issues
from cognite.neat.rules.importers._dtdl2rules.dtdl_converter import _DTDLConverter
from cognite.neat.rules.importers._dtdl2rules.spec import DTDL_CLS_BY_TYPE_BY_SPEC, DTDLBase, Interface
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules.base import SchemaCompleteness, SheetList
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList, ValidationIssue


class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language).

    This importer supports DTDL v2.0 and v3.0.

    It is recommended to use the class methods `from_directory` and `from_zip` to create an instance of this class.

    Args:
        items (Sequence[DTDLBase]): A sequence of DTDLBase objects.
        title (str, optional): Title of the data model. Defaults to None.
        read_issues (list[ValidationIssue], optional): A list of issues that occurred during reading. Defaults to None.
        schema (SchemaCompleteness, optional): Schema completeness. Defaults to SchemaCompleteness.partial.

    """

    def __init__(
        self,
        items: Sequence[DTDLBase],
        title: str | None = None,
        read_issues: list[ValidationIssue] | None = None,
        schema: SchemaCompleteness = SchemaCompleteness.partial,
    ) -> None:
        self._items = items
        self.title = title
        self._read_issues = read_issues
        self._schema_completeness = schema

    @classmethod
    def _from_file_content(cls, file_content: str, filepath: Path) -> Iterable[DTDLBase | ValidationIssue]:
        raw = json.loads(file_content)
        if isinstance(raw, dict):
            if (context := raw.get("@context")) is None:
                yield validation.InvalidFileFormat(filepath=filepath, reason="Missing '@context' key.")
                return
            raw_list = [raw]
        elif isinstance(raw, list):
            context = next(
                (entry["@context"] for entry in raw if isinstance(entry, dict) and "@context" in entry), None
            )
            if context is None:
                yield validation.InvalidFileFormat(filepath=filepath, reason="Missing '@context' key.")
                return
            raw_list = raw
        else:
            yield validation.InvalidFileFormat(filepath=filepath, reason="Content is not an object or array.")
            return

        if isinstance(context, list):
            context = context[0]
        Interface.default_context = context
        spec_version = context.split(";")[1]
        try:
            cls_by_type = DTDL_CLS_BY_TYPE_BY_SPEC[spec_version]
        except KeyError:
            yield validation.UnsupportedSpec(filepath=filepath, version=spec_version, spec_name="DTDL")
            return

        for item in raw_list:
            if not (type_ := item.get("@type")):
                yield validation.InvalidFileFormat(filepath=filepath, reason="Missing '@type' key.")
                continue
            cls_ = cls_by_type.get(type_)
            if cls_ is None:
                yield validation.UnknownItem(reason=f"Unknown '@type' {type_}.", filepath=filepath)
                continue
            try:
                yield cls_.model_validate(item)
            except ValidationError as e:
                yield validation.InvalidFileFormat(filepath=filepath, reason=str(e))
            except Exception as e:
                yield validation.BugInImporter(filepath=filepath, error=str(e), importer_name=cls.__name__)

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        issues: list[ValidationIssue] = []
        for filepath in directory.glob("**/*.json"):
            for item in cls._from_file_content(filepath.read_text(), filepath):
                if isinstance(item, ValidationIssue):
                    issues.append(item)
                else:
                    items.append(item)
        return cls(items, directory.name, read_issues=issues)

    @classmethod
    def from_zip(cls, zip_file: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        issues: list[ValidationIssue] = []
        with zipfile.ZipFile(zip_file) as z:
            for filepath in z.namelist():
                if filepath.endswith(".json"):
                    for item in cls._from_file_content(z.read(filepath).decode(), Path(filepath)):
                        if isinstance(item, ValidationIssue):
                            issues.append(item)
                        else:
                            items.append(item)
        return cls(items, zip_file.name, read_issues=issues)

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        container = _DTDLConverter(self._read_issues)

        container.convert(self._items)

        metadata = self._default_metadata()
        metadata["schema"] = self._schema_completeness.value
        with _handle_issues(container.issues) as future:
            rules = InformationRules(
                metadata=metadata,
                properties=SheetList[InformationProperty](data=container.properties),
                classes=SheetList[InformationClass](data=container.classes),
            )
        if future.result == "failure":
            if errors == "continue":
                return None, container.issues
            else:
                raise container.issues.as_errors()

        return self._to_output(rules, container.issues, errors, role)
