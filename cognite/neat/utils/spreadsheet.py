from typing import Literal, overload

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


@overload
def read_spreadsheet(
    excel_file: pd.ExcelFile,
    sheet_name: str,
    return_header_row: Literal[True],
    expected_headers: list[str] | None = None,
) -> tuple[list[dict], int]:
    ...


@overload
def read_spreadsheet(
    excel_file: pd.ExcelFile,
    sheet_name: str,
    return_header_row: Literal[False] = False,
    expected_headers: list[str] | None = None,
) -> list[dict]:
    ...


def read_spreadsheet(
    excel_file: pd.ExcelFile,
    sheet_name: str,
    return_header_row: bool = False,
    expected_headers: list[str] | None = None,
) -> tuple[list[dict], int] | list[dict]:
    if expected_headers:
        target_row = _get_row_number(load_workbook(excel_file)[sheet_name], expected_headers)
        skiprows = target_row - 1 if target_row is not None else 0
    else:
        skiprows = 0

    output = (
        pd.read_excel(excel_file, sheet_name, skiprows=skiprows)
        .dropna(axis=0, how="all")
        .replace(float("nan"), None)
        .to_dict(orient="records")
    )
    if return_header_row:
        return output, skiprows + 1
    return output


def _get_row_number(sheet: Worksheet, values_to_find: list[str]) -> int | None:
    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if any(value in row for value in values_to_find):
            return row_number
    return None
