"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import UserDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from cognite.client.utils._importing import local_import
from pandas import ExcelFile
from rdflib import Namespace, URIRef

from cognite.neat._issues import IssueList, MultiValueError
from cognite.neat._issues.errors import (
    FileMissingRequiredFieldError,
    FileNotFoundNeatError,
    FileReadError,
)
from cognite.neat._issues.warnings import FileMissingRequiredFieldWarning
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.models import (
    INPUT_RULES_BY_ROLE,
    VERIFIED_RULES_BY_ROLE,
    RoleTypes,
    SchemaCompleteness,
)
from cognite.neat._utils.spreadsheet import SpreadsheetRead, read_individual_sheet
from cognite.neat._utils.text import humanize_collection

from ._base import BaseImporter

SOURCE_SHEET__TARGET_FIELD__HEADERS = [
    (
        "Properties",
        "Properties",
        {
            RoleTypes.information: ["Class", "Property"],
            RoleTypes.dms: ["View", "View Property"],
        },
    ),
    ("Classes", "Classes", ["Class"]),
    ("Containers", "Containers", ["Container"]),
    ("Views", "Views", ["View"]),
    ("Enum", "Enum", ["Collection"]),
    ("Nodes", "Nodes", ["Node"]),
]


MANDATORY_SHEETS_BY_ROLE: dict[RoleTypes, set[str]] = {
    role_type: {
        str(sheet_name)
        for sheet_name in (
            VERIFIED_RULES_BY_ROLE.get(role_type).mandatory_fields(use_alias=True)  # type: ignore
            if VERIFIED_RULES_BY_ROLE.get(role_type)
            else []
        )
        if sheet_name is not None
    }
    for role_type in RoleTypes.__members__.values()
}


class MetadataRaw(UserDict):
    @classmethod
    def from_excel(cls, excel_file: ExcelFile, metadata_sheet_name: str) -> "MetadataRaw":
        return cls(pd.read_excel(excel_file, metadata_sheet_name, header=None).replace(float("nan"), None).values)

    @property
    def has_role_field(self) -> bool:
        return self.get("role") in [role.value for role in RoleTypes.__members__.values()]

    @property
    def role(self) -> RoleTypes:
        return RoleTypes(self["role"])

    @property
    def has_schema_field(self) -> bool:
        return self.get("schema") in [schema.value for schema in SchemaCompleteness.__members__.values()]

    @property
    def schema(self) -> SchemaCompleteness | None:
        if not self.has_schema_field:
            return None
        return SchemaCompleteness(self["schema"])

    def is_valid(self, issue_list: IssueList, filepath: Path) -> bool:
        if not self.has_role_field:
            issue_list.append(FileMissingRequiredFieldError(filepath, "metadata", "role"))
            return False

        return True


@dataclass
class ReadResult:
    sheets: dict[str, dict | list]
    read_info_by_sheet: dict[str, SpreadsheetRead]
    metadata: MetadataRaw
    prefixes: dict[str, Namespace] | None = None

    @property
    def role(self) -> RoleTypes:
        return self.metadata.role

    @property
    def schema(self) -> SchemaCompleteness | None:
        return self.metadata.schema


class SpreadsheetReader:
    def __init__(
        self,
        issue_list: IssueList,
        required: bool = True,
        metadata: MetadataRaw | None = None,
        sheet_prefix: Literal["", "Last", "Ref", "CDMRef"] = "",
    ):
        self.issue_list = issue_list
        self.required = required
        self.metadata = metadata
        self._sheet_prefix = sheet_prefix
        self._seen_files: set[Path] = set()
        self._seen_sheets: set[str] = set()

    @property
    def metadata_sheet_name(self) -> str:
        return f"{self._sheet_prefix}Metadata"

    @property
    def prefixes_sheet_name(self) -> str:
        return "Prefixes"

    @property
    def seen_sheets(self) -> set[str]:
        if not self._seen_files:
            raise ValueError("No files have been read yet.")
        return self._seen_sheets

    def sheet_names(self, role: RoleTypes) -> set[str]:
        names = MANDATORY_SHEETS_BY_ROLE[role]
        return {f"{self._sheet_prefix}{sheet_name}" for sheet_name in names if sheet_name != "Metadata"}

    def read(self, excel_file: pd.ExcelFile, filepath: Path) -> None | ReadResult:
        self._seen_files.add(filepath)
        self._seen_sheets.update(map(str, excel_file.sheet_names))
        metadata: MetadataRaw | None
        if self.metadata is not None:
            metadata = self.metadata
        else:
            metadata = self._read_metadata(excel_file, filepath)
            if metadata is None:
                # The reading of metadata failed, so we can't continue
                return None

        sheets, read_info_by_sheet = self._read_sheets(excel_file, metadata.role)
        if sheets is None or self.issue_list.has_errors:
            return None
        sheets["Metadata"] = dict(metadata)

        # Special case for reading prefixes as they are suppose to be read only once
        if (
            self.prefixes_sheet_name in excel_file.sheet_names
            and not self._sheet_prefix
            and (prefixes := self._read_prefixes(excel_file, filepath))
        ):
            sheets["Prefixes"] = prefixes

        return ReadResult(sheets, read_info_by_sheet, metadata)

    def _read_metadata(self, excel_file: ExcelFile, filepath: Path) -> MetadataRaw | None:
        if self.metadata_sheet_name not in excel_file.sheet_names:
            if self.required:
                self.issue_list.append(FileMissingRequiredFieldError(filepath, "sheet", self.metadata_sheet_name))
            return None

        metadata = MetadataRaw.from_excel(excel_file, self.metadata_sheet_name)

        if not metadata.is_valid(self.issue_list, filepath):
            return None
        return metadata

    def _read_prefixes(self, excel_file: ExcelFile, filepath: Path) -> dict[str, Namespace] | None:
        if self.prefixes_sheet_name not in excel_file.sheet_names:
            return None

        else:
            prefixes = {}

            for row in read_individual_sheet(excel_file, "Prefixes", expected_headers=["Prefix", "Namespace"]):
                if "Prefix" in row and "Namespace" in row:
                    prefixes[row["Prefix"]] = row["Namespace"]
                else:
                    if "Prefix" not in row:
                        self.issue_list.append(FileMissingRequiredFieldWarning(filepath, "prefixes", "prefix"))
                    if "Namespace" not in row:
                        self.issue_list.append(FileMissingRequiredFieldWarning(filepath, "prefixes", "namespace"))
                    return None

            return prefixes

    def _read_sheets(
        self, excel_file: ExcelFile, read_role: RoleTypes
    ) -> tuple[dict[str, dict | list] | None, dict[str, SpreadsheetRead]]:
        read_info_by_sheet: dict[str, SpreadsheetRead] = defaultdict(SpreadsheetRead)

        sheets: dict[str, dict | list] = {}

        expected_sheet_names = self.sheet_names(read_role)

        if missing_sheets := expected_sheet_names.difference(set(excel_file.sheet_names)):
            if self.required:
                self.issue_list.append(
                    FileMissingRequiredFieldError(
                        cast(Path, excel_file.io), "sheets", humanize_collection(missing_sheets)
                    )
                )
            return None, read_info_by_sheet

        for source_sheet_name, target_sheet_name, headers_input in SOURCE_SHEET__TARGET_FIELD__HEADERS:
            source_sheet_name = f"{self._sheet_prefix}{source_sheet_name}"

            if source_sheet_name not in excel_file.sheet_names:
                continue
            if isinstance(headers_input, dict):
                headers = headers_input[read_role]
            else:
                headers = headers_input

            try:
                sheets[target_sheet_name], read_info_by_sheet[source_sheet_name] = read_individual_sheet(
                    excel_file,
                    source_sheet_name,
                    return_read_info=True,
                    expected_headers=headers,
                )
            except Exception as e:
                self.issue_list.append(FileReadError(cast(Path, excel_file.io), str(e)))
                continue

        return sheets, read_info_by_sheet


class ExcelImporter(BaseImporter[T_InputRules]):
    """Import rules from an Excel file.

    Args:
        filepath (Path): The path to the Excel file.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_rules(self) -> ReadRules[T_InputRules]:
        issue_list = IssueList(title=f"'{self.filepath.name}'")
        if not self.filepath.exists():
            raise FileNotFoundNeatError(self.filepath)

        with pd.ExcelFile(self.filepath) as excel_file:
            user_reader = SpreadsheetReader(issue_list)

            user_read = user_reader.read(excel_file, self.filepath)

        issue_list.trigger_warnings()
        if issue_list.has_errors:
            raise MultiValueError(issue_list.errors)

        if user_read is None:
            return ReadRules(None, {})

        sheets = user_read.sheets
        original_role = user_read.role
        read_info_by_sheet = user_read.read_info_by_sheet

        rules_cls = INPUT_RULES_BY_ROLE[original_role]
        rules = cast(T_InputRules, rules_cls.load(sheets))
        return ReadRules(rules, read_info_by_sheet)

    @property
    def description(self) -> str:
        return f"Excel file {self.filepath.name} read as unverified data model"

    @property
    def source_uri(self) -> URIRef:
        return URIRef(f"file://{self.filepath.name}")


class GoogleSheetImporter(BaseImporter[T_InputRules]):
    """Import rules from a Google Sheet.

    .. warning::

        This importer is experimental and may not work as expected.

    Args:
        sheet_id (str): The Google Sheet ID.
        skiprows (int): The number of rows to skip when reading the Google Sheet.
    """

    def __init__(self, sheet_id: str, skiprows: int = 1):
        self.sheet_id = sheet_id
        self.skiprows = skiprows

    def to_rules(self) -> ReadRules[T_InputRules]:
        raise NotImplementedError("Google Sheet Importer is not yet implemented.")

    def _get_sheets(self) -> dict[str, pd.DataFrame]:
        local_import("gspread", "google")
        import gspread  # type: ignore[import]

        client_google = gspread.service_account()
        google_sheet = client_google.open_by_key(self.sheet_id)
        return {worksheet.title: pd.DataFrame(worksheet.get_all_records()) for worksheet in google_sheet.worksheets()}
