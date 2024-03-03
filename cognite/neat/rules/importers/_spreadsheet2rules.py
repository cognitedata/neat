"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""
from collections import defaultdict
from pathlib import Path
from typing import Literal, cast, overload

import pandas as pd
from pydantic import ValidationError

from cognite.neat.rules.models._rules import RULES_PER_ROLE, DMSRules, DomainRules, InformationRules
from cognite.neat.rules.models._rules.base import RoleTypes
from cognite.neat.utils.auxiliary import local_import
from cognite.neat.utils.spreadsheet import read_spreadsheet

from . import _models as issue_cls
from ._base import BaseImporter, Rule
from ._models import IssueList


class ExcelImporter(BaseImporter):
    def __init__(self, filepath: Path):
        self.filepath = filepath

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rule:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rule | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rule | None, IssueList] | Rule:
        issues = IssueList()
        try:
            excel_file = pd.ExcelFile(self.filepath)
        except FileNotFoundError:
            issues.append(issue_cls.SpreadsheetNotFound(self.filepath.name))
            if errors == "raise":
                raise issues.as_errors() from None
            return None, issues

        try:
            metadata = dict(pd.read_excel(excel_file, "Metadata", header=None).values)
        except ValueError:
            issues.append(issue_cls.MetadataSheetMissingOrFailed())
            if errors == "raise":
                raise issues.as_errors() from None
            return None, issues

        role = role or RoleTypes(metadata.get("role", RoleTypes.domain_expert))
        role_enum = RoleTypes(role)
        rules_model = RULES_PER_ROLE[role_enum]
        sheet_names = {str(name) for name in excel_file.sheet_names}
        expected_sheet_names = rules_model.mandatory_fields(use_alias=True)

        if missing_sheets := expected_sheet_names.difference(sheet_names):
            issues.append(issue_cls.SpreadsheetMissing(list(missing_sheets)))
            if errors == "raise":
                raise issues.as_errors()
            return None, issues

        sheets: dict[str, dict | list] = {"Metadata": metadata}
        header_row_no_by_sheet: dict[str, int] = defaultdict(int)
        for sheet_name, headers in [
            ("Properties", "Class"),
            ("Classes", "Class"),
            ("Containers", "Container"),
            ("Views", "View"),
        ]:
            if sheet_name in excel_file.sheet_names:
                try:
                    sheets[sheet_name], header_row_no_by_sheet[sheet_name] = read_spreadsheet(
                        excel_file, sheet_name, return_header_row=True, expected_headers=[headers]
                    )
                except Exception as e:
                    issues.append(issue_cls.ReadSpreadsheets(str(e)))
                    continue
        if issues:
            if errors == "raise":
                raise issues.as_errors()
            return None, issues

        rules_cls = {
            RoleTypes.domain_expert: DomainRules,
            RoleTypes.information_architect: InformationRules,
            RoleTypes.dms_architect: DMSRules,
        }.get(role_enum)
        if not rules_cls:
            issues.append(issue_cls.InvalidRole(str(role)))
            if errors == "raise":
                raise issues.as_errors()
            return None, issues

        try:
            rules = rules_cls.model_validate(sheets)  # type: ignore[attr-defined]
        except ValidationError as e:
            issues.extend(issue_cls.InvalidSheetContent.from_pydantic_errors(e.errors(), header_row_no_by_sheet))
            if errors == "raise":
                raise issues.as_errors() from e
            return None, issues

        if errors == "raise":
            return rules
        return rules, issues


class GoogleSheetImporter(BaseImporter):
    def __init__(self, sheet_id: str, skiprows: int = 1):
        self.sheet_id = sheet_id
        self.skiprows = skiprows

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rule:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rule | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rule | None, IssueList] | Rule:
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
            return rules_model.model_validate(sheets)
        elif role == RoleTypes.information_architect:
            return rules_model.model_validate(sheets)
        elif role == RoleTypes.dms_architect:
            return rules_model.model_validate(sheets)
        else:
            raise ValueError(f"Role {role} is not valid.")
