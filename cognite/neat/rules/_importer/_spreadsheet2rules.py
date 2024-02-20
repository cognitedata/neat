"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from pathlib import Path
from typing import cast

import pandas as pd

from cognite.neat.rules.models._rules import RULES_PER_ROLE, DMSRules, DomainRules, InformationRules
from cognite.neat.rules.models._rules.base import RoleTypes
from cognite.neat.utils.auxiliary import local_import
from cognite.neat.utils.spreadsheet import read_spreadsheet

from ._base import BaseImporter


class ExcelImporter(BaseImporter):
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_rules(self, role: RoleTypes | None = None, skiprows: int = 1) -> DomainRules | InformationRules | DMSRules:
        role = role or RoleTypes.domain_expert
        rules_model = cast(DomainRules | InformationRules | DMSRules, RULES_PER_ROLE[role])
        excel_file = pd.ExcelFile(self.filepath)
        sheet_names = {str(name).lower() for name in excel_file.sheet_names}

        if missing_sheets := rules_model.mandatory_fields().difference(sheet_names):
            raise ValueError(f"Missing mandatory sheets: {missing_sheets}")

        sheets = {
            "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
            "Properties": read_spreadsheet(excel_file, "Properties", skiprows=skiprows),
            "Classes": (
                read_spreadsheet(excel_file, "Classes", skiprows=skiprows)
                if "Classes" in excel_file.sheet_names
                else None
            ),
            "Containers": (
                read_spreadsheet(excel_file, "Containers", skiprows=skiprows)
                if "Containers" in excel_file.sheet_names
                else None
            ),
            "Views": (
                read_spreadsheet(excel_file, "Views", skiprows=skiprows) if "Views" in excel_file.sheet_names else None
            ),
        }
        if role == RoleTypes.domain_expert:
            return rules_model.model_validate(sheets)
        elif role == RoleTypes.information_architect:
            return rules_model.model_validate(sheets)
        elif role == RoleTypes.dms_architect:
            return rules_model.model_validate(sheets)
        else:
            raise ValueError(f"Role {role} is not valid.")


class GoogleSheetImporter(BaseImporter):
    def __init__(self, sheet_id: str):
        self.sheet_id = sheet_id

    def to_rules(self, role: RoleTypes | None = None, skiprows: int = 1) -> DomainRules | InformationRules | DMSRules:
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
