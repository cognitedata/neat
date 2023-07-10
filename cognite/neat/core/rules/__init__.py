from pathlib import Path

from . import _loader, _parser, models

__all__ = [
    "models",
    "load_rules_from_excel_file",
    "load_rules_from_google_sheet",
    "load_rules_from_yaml",
]


def load_rules_from_excel_file(filepath: Path) -> models.TransformationRules:
    """
    Load transformation rules from an Excel file.

    Args:
        filepath (Path): Path to the excel file.
    Returns:
        TransformationRules: The transformation rules.
    """
    return _parser.from_tables(_loader.excel_file_to_table_by_name(filepath))


def load_rules_from_google_sheet(sheet_id: str) -> models.TransformationRules:
    """
    Load transformation rules from a Google sheet.

    Args:
        sheet_id (str): The identifier of the Google sheet with the rules.
    Returns:
        TransformationRules: The transformation rules.
    """
    return _parser.from_tables(_loader.google_to_table_by_name(sheet_id))


def load_rules_from_yaml(dirpath: Path) -> models.TransformationRules:
    """
    Load transformation rules from a yaml file.

    Args:
        dirpath (Path): Path to the yaml file.
    Returns:
        TransformationRules: The transformation rules.
    """
    return models.TransformationRules(**_loader.yaml_file_to_mapping_by_name(dirpath))
