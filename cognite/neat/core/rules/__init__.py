from pathlib import Path

from . import models
from ._loader import excel_file_to_table_by_name, google_to_table_by_name
from ._parser import parse_transformation_rules

__all__ = [
    "models",
    "load_rules_from_excel_file",
    "load_rules_from_google_sheet",
]


def load_rules_from_excel_file(filepath: Path) -> models.TransformationRules:
    """
    Load transformation rules from an Excel file.

    Args:
        filepath (Path): Path to the excel file.
    Returns:
        TransformationRules: The transformation rules.
    """
    return parse_transformation_rules(excel_file_to_table_by_name(filepath))


def load_rules_from_google_sheet(sheet_id: str) -> models.TransformationRules:
    """
    Load transformation rules from a Google sheet.

    Args:
        sheet_id (str): The identifier of the Google sheet with the rules.
    Returns:
        TransformationRules: The transformation rules.
    """
    return parse_transformation_rules(google_to_table_by_name(sheet_id))
