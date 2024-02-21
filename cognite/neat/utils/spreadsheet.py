from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


def read_spreadsheet(excel_file: pd.ExcelFile, sheet_name: str, values_to_find: list[str]) -> list[Any]:
    target_row = get_row_number(load_workbook(excel_file)[sheet_name], values_to_find)
    skiprows = target_row if target_row else 0

    return (
        pd.read_excel(excel_file, sheet_name, skiprows=skiprows)
        .dropna(axis=0, how="all")
        .replace(float("nan"), None)
        .to_dict(orient="records")
    )


def get_row_number(sheet: Worksheet, values_to_find: list[str]):
    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if any(value in row for value in values_to_find):
            return row_number - 1
    return None
