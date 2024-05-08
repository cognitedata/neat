"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import UserDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, overload

import pandas as pd
from pandas import ExcelFile

from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models import (
    RULES_PER_ROLE,
    DMSRules,
    DomainRules,
    InformationRules,
    RoleTypes,
    SchemaCompleteness,
)
from cognite.neat.rules.models.dms import DMSRulesInput
from cognite.neat.utils.auxiliary import local_import
from cognite.neat.utils.spreadsheet import SpreadsheetRead, read_individual_sheet

from ._base import BaseImporter, Rules, _handle_issues

SOURCE_SHEET__TARGET_FIELD__HEADERS = [
    (
        "Properties",
        "Properties",
        {
            RoleTypes.domain_expert: "Property",
            RoleTypes.information_architect: "Property",
            RoleTypes.dms_architect: "View Property",
        },
    ),
    ("Classes", "Classes", "Class"),
    ("Containers", "Containers", "Container"),
    ("Views", "Views", "View"),
]

MANDATORY_SHEETS_BY_ROLE: dict[RoleTypes, set[str]] = {
    role_type: {str(sheet_name) for sheet_name in RULES_PER_ROLE[role_type].mandatory_fields(use_alias=True)}
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
            issue_list.append(issues.spreadsheet_file.RoleMissingOrUnsupportedError(filepath))
            return False

        # check if there is a schema field if role is not domain expert
        if self.role != RoleTypes.domain_expert and not self.has_schema_field:
            issue_list.append(issues.spreadsheet_file.SchemaMissingOrUnsupportedError(filepath))
            return False
        return True


@dataclass
class ReadResult:
    sheets: dict[str, dict | list]
    read_info_by_sheet: dict[str, SpreadsheetRead]
    role: RoleTypes
    schema: SchemaCompleteness | None


class SpreadsheetReader:
    def __init__(
        self, issue_list: IssueList, metadata: MetadataRaw | None = None, sheet_prefix: Literal["", "Last", "Ref"] = ""
    ):
        self.issue_list = issue_list
        self.metadata = metadata
        self._sheet_prefix = sheet_prefix

    @property
    def metadata_sheet_name(self) -> str:
        return f"{self._sheet_prefix}Metadata"

    def sheet_names(self, role: RoleTypes) -> set[str]:
        names = MANDATORY_SHEETS_BY_ROLE[role]
        return {f"{self._sheet_prefix}{sheet_name}" for sheet_name in names}

    def read(self, filepath: Path) -> None | ReadResult:
        with pd.ExcelFile(filepath) as excel_file:
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

            return ReadResult(sheets, read_info_by_sheet, metadata.role, metadata.schema)

    def _read_metadata(self, excel_file: ExcelFile, filepath: Path) -> MetadataRaw | None:
        if self.metadata_sheet_name not in excel_file.sheet_names:
            self.issue_list.append(
                issues.spreadsheet_file.MetadataSheetMissingOrFailedError(filepath, sheet_name=self.metadata_sheet_name)
            )
            return None

        metadata = MetadataRaw.from_excel(excel_file, self.metadata_sheet_name)

        if not metadata.is_valid(self.issue_list, filepath):
            return None
        return metadata

    def _read_sheets(
        self, excel_file: ExcelFile, read_role: RoleTypes
    ) -> tuple[dict[str, dict | list] | None, dict[str, SpreadsheetRead]]:
        read_info_by_sheet: dict[str, SpreadsheetRead] = defaultdict(SpreadsheetRead)

        sheets: dict[str, dict | list] = {}

        expected_sheet_names = self.sheet_names(read_role)

        if missing_sheets := expected_sheet_names.difference(set(excel_file.sheet_names)):
            self.issue_list.append(
                issues.spreadsheet_file.SheetMissingError(cast(Path, excel_file.io), list(missing_sheets))
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
                    excel_file, source_sheet_name, return_read_info=True, expected_headers=[headers]
                )
            except Exception as e:
                self.issue_list.append(issues.spreadsheet_file.ReadSpreadsheetsError(cast(Path, excel_file.io), str(e)))
                continue

        return sheets, read_info_by_sheet


class ExcelImporter(BaseImporter):
    def __init__(self, filepath: Path):
        self.filepath = filepath

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self,
        errors: Literal["continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        issue_list = IssueList(title=f"'{self.filepath.name}'")
        if not self.filepath.exists():
            issue_list.append(issues.spreadsheet_file.SpreadsheetNotFoundError(self.filepath))
            return self._return_or_raise(issue_list, errors)

        user_result = SpreadsheetReader(issue_list).read(self.filepath)
        if user_result is None or issue_list.has_errors:
            return self._return_or_raise(issue_list, errors)

        reference_result: ReadResult | None = None
        if user_result.schema == SchemaCompleteness.extended:
            reference_result = SpreadsheetReader(issue_list, sheet_prefix="Ref").read(self.filepath)
            if issue_list.has_errors:
                return self._return_or_raise(issue_list, errors)

        if user_result and reference_result and user_result.role != reference_result.role:
            issue_list.append(issues.spreadsheet_file.RoleMismatchError(self.filepath))
            return self._return_or_raise(issue_list, errors)

        sheets = user_result.sheets
        original_role = user_result.role
        read_info_by_sheet = user_result.read_info_by_sheet
        if reference_result:
            sheets["reference"] = reference_result.sheets
            read_info_by_sheet.update(reference_result.read_info_by_sheet)

        rules_cls = RULES_PER_ROLE[original_role]
        with _handle_issues(
            issue_list,
            error_cls=issues.spreadsheet.InvalidSheetError,
            error_args={"read_info_by_sheet": read_info_by_sheet},
        ) as future:
            rules: Rules
            if rules_cls is DMSRules:
                rules = DMSRulesInput.load(sheets).as_rules()
            else:
                rules = rules_cls.model_validate(sheets)  # type: ignore[attr-defined]

        if future.result == "failure" or issue_list.has_errors:
            return self._return_or_raise(issue_list, errors)

        return self._to_output(
            rules,
            issue_list,
            errors=errors,
            role=role,
        )


class GoogleSheetImporter(BaseImporter):
    def __init__(self, sheet_id: str, skiprows: int = 1):
        self.sheet_id = sheet_id
        self.skiprows = skiprows

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        local_import("gspread", "google")
        import gspread  # type: ignore[import]

        role = role or RoleTypes.domain_expert
        rules_model = cast(DomainRules | InformationRules | DMSRules, RULES_PER_ROLE[role])

        client_google = gspread.service_account()
        google_sheet = client_google.open_by_key(self.sheet_id)
        sheets = {worksheet.title: pd.DataFrame(worksheet.get_all_records()) for worksheet in google_sheet.worksheets()}
        sheet_names = {str(name).lower() for name in sheets.keys()}

        if missing_sheets := rules_model.mandatory_fields().difference(sheet_names):
            raise ValueError(f"Missing mandatory sheets: {missing_sheets}")

        if role == RoleTypes.domain_expert:
            output = rules_model.model_validate(sheets)
        elif role == RoleTypes.information_architect:
            output = rules_model.model_validate(sheets)
        elif role == RoleTypes.dms_architect:
            output = rules_model.model_validate(sheets)
        else:
            raise ValueError(f"Role {role} is not valid.")

        return self._to_output(output, IssueList(), errors=errors, role=role)
