from typing import Any

import pandas as pd


def read_spreadsheet(excel_file: pd.ExcelFile, sheet_name: str, skiprows: int = 0) -> list[Any]:
    return (
        pd.read_excel(excel_file, sheet_name, skiprows=skiprows)
        .dropna(axis=0, how="all")
        .replace(float("nan"), None)
        .to_dict(orient="records")
    )
