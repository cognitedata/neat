import json
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import ValidationError

from cognite.neat._issues import IssueList, MultiValueError, NeatIssue
from cognite.neat._issues.warnings import (
    FileItemNotSupportedWarning,
    FileMissingRequiredFieldWarning,
    FileReadWarning,
    FileTypeUnexpectedWarning,
    NeatValueWarning,
)
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._base import BaseImporter
from cognite.neat._rules.importers._dtdl2rules.dtdl_converter import _DTDLConverter
from cognite.neat._rules.importers._dtdl2rules.spec import DTDL_CLS_BY_TYPE_BY_SPEC, DTDLBase, Interface
from cognite.neat._rules.models import InformationInputRules
from cognite.neat._rules.models.information import InformationInputMetadata
from cognite.neat._utils.text import humanize_collection, to_pascal_case


class DTDLImporter(BaseImporter[InformationInputRules]):
    """Importer from Azure Digital Twin - DTDL (Digital Twin Definition Language).

    This importer supports DTDL v2.0 and v3.0.

    It is recommended to use the class methods `from_directory` and `from_zip` to create an instance of this class.

    Args:
        items (Sequence[DTDLBase]): A sequence of DTDLBase objects.
        name (str, optional): Name of the data model. Defaults to None.
        read_issues (list[ValidationIssue], optional): A list of issues that occurred during reading. Defaults to None.
        schema (SchemaCompleteness, optional): Schema completeness. Defaults to SchemaCompleteness.partial.

    """

    def __init__(
        self,
        items: Sequence[DTDLBase],
        name: str | None = None,
        read_issues: list[NeatIssue] | None = None,
    ) -> None:
        self._items = items
        self.name = name
        self._read_issues = IssueList(read_issues)

    @classmethod
    def _from_file_content(cls, file_content: str, filepath: Path) -> Iterable[DTDLBase | NeatIssue]:
        raw = json.loads(file_content)
        if isinstance(raw, dict):
            if (context := raw.get("@context")) is None:
                yield FileMissingRequiredFieldWarning(filepath, "@context", "Missing '@context' key.")
                return
            raw_list = [raw]
        elif isinstance(raw, list):
            context = next(
                (entry["@context"] for entry in raw if isinstance(entry, dict) and "@context" in entry), None
            )
            if context is None:
                yield FileMissingRequiredFieldWarning(filepath, "@context", "Missing '@context' key.")
                return
            raw_list = raw
        else:
            yield FileTypeUnexpectedWarning(filepath, frozenset(["dict", "list"]), "Content is not an object or array.")
            return

        if isinstance(context, list):
            context = context[0]
        Interface.default_context = context
        spec_version = context.split(";")[1]
        try:
            cls_by_type = DTDL_CLS_BY_TYPE_BY_SPEC[spec_version]
        except KeyError:
            yield NeatValueWarning(
                f"Unsupported DTDL spec version: {spec_version} in {filepath}. "
                f"Supported versions are {humanize_collection(DTDL_CLS_BY_TYPE_BY_SPEC.keys())}."
                " The file will be skipped."
            )
            return

        for item in raw_list:
            if not (type_ := item.get("@type")):
                yield FileMissingRequiredFieldWarning(filepath, "@type", "Missing '@type' key.")
                continue
            cls_ = cls_by_type.get(type_)
            if cls_ is None:
                yield FileItemNotSupportedWarning(f"Unknown '@type' {type_}.", filepath=filepath)
                continue
            try:
                yield cls_.model_validate(item)
            except ValidationError as e:
                yield FileTypeUnexpectedWarning(filepath, frozenset([cls.__name__]), str(e))
            except Exception as e:
                yield FileReadWarning(filepath=filepath, reason=str(e))

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        issues: list[NeatIssue] = []
        for filepath in directory.glob("**/*.json"):
            for item in cls._from_file_content(filepath.read_text(), filepath):
                if isinstance(item, NeatIssue):
                    issues.append(item)
                else:
                    items.append(item)
        return cls(items, directory.stem, read_issues=issues)

    @classmethod
    def from_zip(cls, zip_file: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        issues: list[NeatIssue] = []
        with zipfile.ZipFile(zip_file) as z:
            for filepath in z.namelist():
                if filepath.endswith(".json"):
                    for item in cls._from_file_content(z.read(filepath).decode(), Path(filepath)):
                        if isinstance(item, NeatIssue):
                            issues.append(item)
                        else:
                            items.append(item)
        return cls(items, zip_file.stem, read_issues=issues)

    def to_rules(self) -> ReadRules[InformationInputRules]:
        converter = _DTDLConverter(self._read_issues)

        converter.convert(self._items)

        metadata = self._default_metadata()

        if self.name:
            metadata["name"] = to_pascal_case(self.name)
        try:
            most_common_prefix = converter.get_most_common_prefix()
        except ValueError:
            # No prefixes are defined so we just use the default prefix...
            ...
        else:
            metadata["space"] = most_common_prefix

        rules = InformationInputRules(
            metadata=InformationInputMetadata.load(metadata),
            properties=converter.properties,
            classes=converter.classes,
        )
        converter.issues.trigger_warnings()
        if converter.issues.has_errors:
            raise MultiValueError(converter.issues.errors)

        return ReadRules(rules, {})
