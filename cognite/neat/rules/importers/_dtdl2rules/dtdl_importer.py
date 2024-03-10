import json
import warnings
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, overload

from pydantic import ValidationError

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.importers._base import BaseImporter, _handle_issues
from cognite.neat.rules.importers._dtdl2rules.dtdl_converter import _DTDLConverter
from cognite.neat.rules.importers._dtdl2rules.spec import DTDL_CLS_BY_TYPE_BY_SPEC, DTDLBase, Interface
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules.base import SchemaCompleteness, SheetList
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList


class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language) files. It can import a directory containing DTDL files and
    convert them to InformationRules.

    The DTDL v3 standard is supported and defined at
    https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md

    Args:
        items (Sequence[DTDLBase]): A sequence of DTDLBase objects.
        title (str, optional): Title of the data model. Defaults to None.
        schema (SchemaCompleteness, optional): Schema completeness. Defaults to SchemaCompleteness.partial.

    """

    def __init__(
        self,
        items: Sequence[DTDLBase],
        title: str | None = None,
        schema: SchemaCompleteness = SchemaCompleteness.partial,
    ) -> None:
        self._items = items
        self.title = title
        self._schema_completeness = schema

    @classmethod
    def _from_file_content(cls, file_content: str, filepath: Path) -> Iterable[DTDLBase]:
        raw = json.loads(file_content)
        if isinstance(raw, dict):
            if (context := raw.get("@context")) is None:
                warnings.warn(f"Invalid json file {filepath}: Missing '@context' key.", stacklevel=2)
                return
            raw_list = [raw]
        elif isinstance(raw, list):
            context = next(
                (entry["@context"] for entry in raw if isinstance(entry, dict) and "@context" in entry), None
            )
            if context is None:
                warnings.warn(f"Invalid json file {filepath}: Missing '@context' key.", stacklevel=2)
                return
            raw_list = raw
        else:
            warnings.warn(f"Invalid json file {filepath}: Content is not an object or array.", stacklevel=2)
            return
        Interface.default_context = context
        spec_version = context.split(";")[1]
        try:
            cls_by_type = DTDL_CLS_BY_TYPE_BY_SPEC[spec_version]
        except KeyError:
            warnings.warn(f"Unsupported DTDL version {spec_version} in  file {filepath}.", stacklevel=2)
            return

        for item in raw_list:
            if not (type_ := item.get("@type")):
                warnings.warn(f"Invalid json file {filepath}: Missing '@type' key.", stacklevel=2)
                continue
            cls_ = cls_by_type.get(type_)
            if cls_ is None:
                warnings.warn(f"Invalid json file {filepath}: Unknown '@type' {type_}.", stacklevel=2)
                continue
            try:
                yield cls_.model_validate(item)
            except ValidationError as e:
                warnings.warn(f"Invalid json file {filepath}: {e!s}.", stacklevel=2)
            except Exception as e:
                warnings.warn(
                    f"Bug in {cls.__name__} triggered in " f"validation of json file {filepath}: {e!s}.", stacklevel=2
                )

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        for filepath in directory.glob("**/*.json"):
            for item in cls._from_file_content(filepath.read_text(), filepath):
                items.append(item)
        return cls(items, directory.name)

    @classmethod
    def from_zip(cls, zip_file: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        with zipfile.ZipFile(zip_file) as z:
            for filepath in z.namelist():
                if filepath.endswith(".json"):
                    for item in cls._from_file_content(z.read(filepath).decode(), Path(filepath)):
                        items.append(item)
        return cls(items, zip_file.name)

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
        container = _DTDLConverter()

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
