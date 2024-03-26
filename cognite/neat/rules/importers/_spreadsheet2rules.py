"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import defaultdict
from pathlib import Path
from typing import Literal, cast, overload

import pandas as pd
from pandas import ExcelFile

import cognite.neat.rules.issues.spreadsheet_file
from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._rules import RULES_PER_ROLE, DMSRules, DomainRules, InformationRules
from cognite.neat.rules.models._rules.base import RoleTypes, SchemaCompleteness
from cognite.neat.utils.auxiliary import local_import
from cognite.neat.utils.spreadsheet import SpreadsheetRead, read_individual_sheet

from ._base import BaseImporter, Rules, _handle_issues

SPREADSHEET_READ_CONFIG = {
    "user": [
        ("Properties", "Properties", "Class"),
        ("Classes", "Classes", "Class"),
        ("Containers", "Containers", "Container"),
        ("Views", "Views", "View"),
    ],
    "reference": [
        ("ReferenceProperties", "Properties", "Class"),
        ("ReferenceClasses", "Classes", "Class"),
        ("ReferenceContainers", "Containers", "Container"),
        ("ReferenceViews", "Views", "View"),
    ],
}

MANDATORY_SHEETS_PER_ROLE: dict[RoleTypes, set[str]] = {
    RoleTypes.domain_expert: {
        str(sheet_name) for sheet_name in RULES_PER_ROLE[RoleTypes.domain_expert].mandatory_fields(use_alias=True)
    },
    RoleTypes.information_architect: {
        str(sheet_name)
        for sheet_name in RULES_PER_ROLE[RoleTypes.information_architect].mandatory_fields(use_alias=True)
    },
    RoleTypes.dms_architect: {
        str(sheet_name) for sheet_name in RULES_PER_ROLE[RoleTypes.dms_architect].mandatory_fields(use_alias=True)
    },
}


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
        # placeholder for variables
        user_metadata: dict = {}
        reference_metadata: dict = {}
        user_sheets: dict[str, dict | list] | None = {}
        reference_sheets: dict[str, dict | list] | None = {}
        user_rules: None | DMSRules | DomainRules | InformationRules = None
        reference_rules: None | DMSRules | DomainRules | InformationRules = None

        issue_list = IssueList(title=f"'{self.filepath.name}'")

        if not self.filepath.exists():
            issue_list.append(cognite.neat.rules.issues.spreadsheet_file.SpreadsheetNotFoundError(self.filepath))
            if error_handling == "raise":
                raise issue_list.as_errors() from None
            return None, issue_list

        with pd.ExcelFile(self.filepath) as excel_file:
            # here we get validated metadata and reference metadata

            if not is_reference:
                user_metadata, issue_list = _get_metadata("Metadata", excel_file, issue_list)
                if issue_list:
                    if error_handling == "raise":
                        raise issue_list.as_errors()
                    return None, issue_list

                schema = user_metadata.get("schema", None)

                if schema and schema == SchemaCompleteness.extended and not is_reference:
                    reference_metadata, issue_list = _get_metadata("ReferenceMetadata", excel_file, issue_list)
                    if issue_list:
                        if error_handling == "raise":
                            raise issue_list.as_errors()
                        return None, issue_list

            else:
                reference_metadata, issue_list = _get_metadata("ReferenceMetadata", excel_file, issue_list)
                if issue_list:
                    if error_handling == "raise":
                        raise issue_list.as_errors()
                    return None, issue_list

            #########################################
            ######## roles must be the same #########

            if user_metadata and reference_metadata:
                if user_metadata.get("role") != reference_metadata.get("role"):
                    issue_list.append(cognite.neat.rules.issues.spreadsheet_file.RoleMismatchError(self.filepath))
                    if error_handling == "raise":
                        raise issue_list.as_errors()
                    return None, issue_list

            #################################################
            ######## checking if sheets are correct #########

            if user_metadata:
                user_sheets, read_info_by_user_sheet, issue_list = _read_sheets(
                    user_metadata, excel_file, "user", issue_list
                )
                if issue_list:
                    if error_handling == "raise":
                        raise issue_list.as_errors()
                    return None, issue_list

            if reference_metadata:
                reference_sheets, read_info_by_reference_sheet, issue_list = _read_sheets(
                    reference_metadata, excel_file, "reference", issue_list
                )
                if issue_list:
                    if error_handling == "raise":
                        raise issue_list.as_errors()
                    return None, issue_list

            #################################################
            ######## checking if rules are correct ##########

            if user_sheets:
                rules_cls = RULES_PER_ROLE[RoleTypes(cast(str, user_metadata.get("role")))]
                with _handle_issues(
                    issue_list,
                    error_cls=issues.spreadsheet.InvalidSheetError,
                    error_args={"read_info_by_sheet": read_info_by_user_sheet},
                ) as future:
                    user_rules = rules_cls.model_validate(user_sheets)  # type: ignore[attr-defined]
                if future.result == "failure":
                    if error_handling == "continue":
                        return None, issue_list
                    else:
                        raise issue_list.as_errors()

            if reference_sheets:
                rules_cls = RULES_PER_ROLE[RoleTypes(cast(str, reference_metadata.get("role")))]
                with _handle_issues(
                    issue_list,
                    error_cls=issues.spreadsheet.InvalidSheetError,
                    error_args={"read_info_by_sheet": read_info_by_reference_sheet},
                ) as future:
                    reference_rules = rules_cls.model_validate(reference_sheets)  # type: ignore[attr-defined]
                if future.result == "failure":
                    if error_handling == "continue":
                        return None, issue_list
                    else:
                        raise issue_list.as_errors()

            # check if reference and user rules are for the same profile if not raise error

        return self._to_output(
            cast(DomainRules | InformationRules | DMSRules, reference_rules if is_reference else user_rules),
            issue_list,
            errors=error_handling,
            role=role,
            is_reference=is_reference,
        )


def _is_there_metadata_sheet(
    metadata_sheet_name: str,
    excel_file: ExcelFile,
):
    return metadata_sheet_name in excel_file.sheet_names


def _is_there_role_field(metadata):
    return metadata.get("role", "") in [role.value for role in RoleTypes]


def _is_there_schema_field(metadata):
    return metadata.get("schema", "") in [schema.value for schema in SchemaCompleteness]


def _get_metadata(metadata_sheet_name: str, excel_file, issue_list) -> tuple[dict, IssueList]:
    # Check if there is a base metadata sheet
    if not _is_there_metadata_sheet(metadata_sheet_name, excel_file):
        issue_list.append(
            cognite.neat.rules.issues.spreadsheet_file.MetadataSheetMissingOrFailedError(
                excel_file.io, sheet_name=metadata_sheet_name
            )
        )
        return {}, issue_list
    else:
        metadata = dict(pd.read_excel(excel_file, metadata_sheet_name, header=None).replace(float("nan"), None).values)

    # check if there is a role field
    if not _is_there_role_field(metadata):
        issue_list.append(cognite.neat.rules.issues.spreadsheet_file.RoleMissingOrUnsupportedError(excel_file.io))
        return {}, issue_list
    else:
        role_input = RoleTypes(cast(str, metadata.get("role")))

    # check if there is a schema field if role is not domain expert
    if role_input != RoleTypes.domain_expert:
        if not _is_there_schema_field(metadata):
            issue_list.append(cognite.neat.rules.issues.spreadsheet_file.SchemaMissingOrUnsupportedError(excel_file.io))
            return {}, issue_list

    return metadata, issue_list


def _read_sheets(
    metadata, excel_file: ExcelFile, sheet_category: str, issue_list
) -> tuple[dict[str, dict | list] | None, dict[str, SpreadsheetRead] | None, IssueList]:
    read_info_by_sheet: dict[str, SpreadsheetRead] = defaultdict(SpreadsheetRead)
    sheets: dict[str, dict | list] = {"Metadata": metadata}
    expected_sheet_names = (
        {f"Reference{sheet_name}" for sheet_name in MANDATORY_SHEETS_PER_ROLE[RoleTypes(metadata.get("role"))]}
        if sheet_category == "reference"
        else MANDATORY_SHEETS_PER_ROLE[RoleTypes(metadata.get("role"))]
    )

    if missing_sheets := expected_sheet_names.difference(set(excel_file.sheet_names)):
        issue_list.append(
            cognite.neat.rules.issues.spreadsheet_file.SheetMissingError(
                cast(Path, excel_file.io), list(missing_sheets)
            )
        )
        return None, None, issue_list

    for source_sheet_name, target_sheet_name, headers in SPREADSHEET_READ_CONFIG[sheet_category]:
        if source_sheet_name in excel_file.sheet_names:
            try:
                sheets[target_sheet_name], read_info_by_sheet[source_sheet_name] = read_individual_sheet(
                    excel_file, source_sheet_name, return_read_info=True, expected_headers=[headers]
                )
            except Exception as e:
                issue_list.append(
                    cognite.neat.rules.issues.spreadsheet_file.ReadSpreadsheetsError(cast(Path, excel_file.io), str(e))
                )
                continue

    return sheets, read_info_by_sheet, issue_list


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
