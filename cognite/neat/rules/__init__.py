from pathlib import Path
from typing import Literal, overload

from pydantic_core import ErrorDetails

from . import _loader, _parser, models


__all__ = [
    "models",
    "load_rules_from_excel_file",
    "load_rules_from_google_sheet",
    "load_rules_from_yaml",
]


@overload
def load_rules_from_excel_file(filepath: Path, return_report: Literal[False] = False) -> models.TransformationRules:
    ...


@overload
def load_rules_from_excel_file(
    filepath: Path, return_report: Literal[True]
) -> tuple[models.TransformationRules | None, list[ErrorDetails] | None, list | None]:
    ...


def load_rules_from_excel_file(
    filepath: Path, return_report: bool = False
) -> tuple[models.TransformationRules | None, list[ErrorDetails] | None, list | None] | models.TransformationRules:
    """
    Load transformation rules from an Excel file.

    Args:
        filepath (Path): Path to the Excel file.
        return_report (bool, optional): Whether to return a report. Defaults to False.

    Returns:
        TransformationRules: The transformation rules.
    """
    return _parser.from_tables(_loader.excel_file_to_table_by_name(filepath), return_report)


def load_rules_from_google_sheet(
    sheet_id: str, return_report: bool = False
) -> tuple[models.TransformationRules | None, list[ErrorDetails] | None, list | None] | models.TransformationRules:
    """
    Load transformation rules from a Google sheet.

    Args:
        sheet_id (str): The identifier of the Google sheet with the rules.
    Returns:
        TransformationRules: The transformation rules.
    """
    return _parser.from_tables(_loader.google_to_table_by_name(sheet_id), return_report)


def load_rules_from_yaml(dirpath: Path) -> models.TransformationRules:
    """
    Load transformation rules from a yaml file.

    Args:
        dirpath (Path): Path to the yaml file.
    Returns:
        TransformationRules: The transformation rules.
    """
    return models.TransformationRules(**_loader.yaml_file_to_mapping_by_name(dirpath))
