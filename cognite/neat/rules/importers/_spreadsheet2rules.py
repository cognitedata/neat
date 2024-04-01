"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import UserDict, defaultdict
from pathlib import Path
from typing import Literal, cast, overload

import pandas as pd
from pandas import ExcelFile

from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._rules import RULES_PER_ROLE, DMSRules, DomainRules, InformationRules
from cognite.neat.rules.models._rules.base import RoleTypes, SchemaCompleteness
from cognite.neat.utils.auxiliary import local_import
from cognite.neat.utils.spreadsheet import SpreadsheetRead, read_individual_sheet

from ._base import BaseImporter, Rules, _handle_issues

SOURCE_SHEET__TARGET_FIELD__HEADERS = [
    ("Properties", "Properties", "Class"),
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

    def is_valid(self, issue_list: IssueList, filepath: Path) -> bool:
        if not self.has_role_field:
            issue_list.append(issues.spreadsheet_file.RoleMissingOrUnsupportedError(filepath))
            return False

        # check if there is a schema field if role is not domain expert
        if self.role != RoleTypes.domain_expert and not self.has_schema_field:
            issue_list.append(issues.spreadsheet_file.SchemaMissingOrUnsupportedError(filepath))
            return False
        return True


class SpreadsheetReader:
    def __init__(self, issue_list: IssueList, is_reference: bool = False):
        self.issue_list = issue_list
        self._is_reference = is_reference

    @property
    def metadata_sheet_name(self) -> str:
        metadata_name = "Metadata"
        return self.to_reference_sheet(metadata_name) if self._is_reference else metadata_name

    def sheet_names(self, role: RoleTypes) -> set[str]:
        names = MANDATORY_SHEETS_BY_ROLE[role]
        return {self.to_reference_sheet(sheet_name) for sheet_name in names} if self._is_reference else names

    @classmethod
    def to_reference_sheet(cls, sheet_name: str) -> str:
        return f"Reference{sheet_name}"

    def read(self, filepath: Path) -> Rules | None:
        with pd.ExcelFile(filepath) as excel_file:
            if self.metadata_sheet_name not in excel_file.sheet_names:
                self.issue_list.append(
                    issues.spreadsheet_file.MetadataSheetMissingOrFailedError(
                        filepath, sheet_name=self.metadata_sheet_name
                    )
                )
                return None

            metadata = MetadataRaw.from_excel(excel_file, self.metadata_sheet_name)

            if not metadata.is_valid(self.issue_list, filepath):
                return None

            sheets, read_info_by_sheet = self._read_sheets(metadata, excel_file)
            if self.issue_list.has_errors:
                return None

            rules_cls = RULES_PER_ROLE[metadata.role]
            with _handle_issues(
                self.issue_list,
                error_cls=issues.spreadsheet.InvalidSheetError,
                error_args={"read_info_by_sheet": read_info_by_sheet},
            ) as future:
                rules = rules_cls.model_validate(sheets)  # type: ignore[attr-defined]

            if future.result == "failure" or self.issue_list.has_errors:
                return None

        return rules

    def _read_sheets(
        self, metadata: MetadataRaw, excel_file: ExcelFile
    ) -> tuple[dict[str, dict | list] | None, dict[str, SpreadsheetRead]]:
        read_info_by_sheet: dict[str, SpreadsheetRead] = defaultdict(SpreadsheetRead)

        sheets: dict[str, dict | list] = {"Metadata": dict(metadata)}

        expected_sheet_names = self.sheet_names(metadata.role)

        if missing_sheets := expected_sheet_names.difference(set(excel_file.sheet_names)):
            self.issue_list.append(
                issues.spreadsheet_file.SheetMissingError(cast(Path, excel_file.io), list(missing_sheets))
            )
            return None, read_info_by_sheet

        for source_sheet_name, target_sheet_name, headers in SOURCE_SHEET__TARGET_FIELD__HEADERS:
            source_sheet_name = self.to_reference_sheet(source_sheet_name) if self._is_reference else source_sheet_name

            if source_sheet_name not in excel_file.sheet_names:
                continue

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
    def to_rules(
        self, error_handling: Literal["raise"], role: RoleTypes | None = None, is_reference: bool = False
    ) -> Rules:
        ...

    @overload
    def to_rules(
        self,
        error_handling: Literal["continue"] = "continue",
        role: RoleTypes | None = None,
        is_reference: bool = False,
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self,
        error_handling: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
        is_reference: bool = False,
    ) -> tuple[Rules | None, IssueList] | Rules:
        issue_list = IssueList(title=f"'{self.filepath.name}'")

        if not self.filepath.exists():
            issue_list.append(issues.spreadsheet_file.SpreadsheetNotFoundError(self.filepath))
            return self._return_or_raise(issue_list, error_handling)

        user_rules: Rules | None = None
        if not is_reference:
            user_rules = SpreadsheetReader(issue_list, is_reference=False).read(self.filepath)
            if issue_list.has_errors:
                return self._return_or_raise(issue_list, error_handling)

        reference_rules: Rules | None = None
        if is_reference or (
            user_rules
            and user_rules.metadata.role != RoleTypes.domain_expert
            and cast(DMSRules | InformationRules, user_rules).metadata.schema_ == SchemaCompleteness.extended
        ):
            reference_rules = SpreadsheetReader(issue_list, is_reference=True).read(self.filepath)
            if issue_list.has_errors:
                return self._return_or_raise(issue_list, error_handling)

        if user_rules and reference_rules and user_rules.metadata.role != reference_rules.metadata.role:
            issue_list.append(issues.spreadsheet_file.RoleMismatchError(self.filepath))
            return self._return_or_raise(issue_list, error_handling)

        if user_rules and reference_rules:
            rules = user_rules
            rules.reference = reference_rules
        elif user_rules:
            rules = user_rules
        elif reference_rules:
            rules = reference_rules
        else:
            raise ValueError(
                "No rules were generated. This should have been caught earlier. " f"Bug in {type(self).__name__}."
            )

        return self._to_output(
            rules,
            issue_list,
            errors=error_handling,
            role=role,
            is_reference=is_reference,
        )

    @classmethod
    def _return_or_raise(
        cls, issue_list: IssueList, error_handling: Literal["raise", "continue"]
    ) -> tuple[None, IssueList]:
        if error_handling == "raise":
            raise issue_list.as_errors()
        return None, issue_list


class GoogleSheetImporter(BaseImporter):
    def __init__(self, sheet_id: str, skiprows: int = 1):
        self.sheet_id = sheet_id
        self.skiprows = skiprows

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None, is_reference: bool = False) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None, is_reference: bool = False
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self,
        errors: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
        is_reference: bool = False,
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

        return self._to_output(output, IssueList(), errors=errors, role=role, is_reference=is_reference)
