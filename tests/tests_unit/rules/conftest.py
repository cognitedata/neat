from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules import DMSRules, InformationRules
from cognite.neat.utils.spreadsheet import read_spreadsheet
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


@pytest.fixture(scope="session")
def alice_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_spreadsheet(excel_file, "Properties", ["Property"]),
        "Views": read_spreadsheet(excel_file, "Views", ["View"]),
        "Containers": read_spreadsheet(excel_file, "Containers", ["Container"]),
    }


@pytest.fixture(scope="session")
def alice_rules(alice_spreadsheet: dict[str, dict[str, Any]]) -> DMSRules:
    return DMSRules.model_validate(alice_spreadsheet)


@pytest.fixture(scope="session")
def david_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "information-architect-david.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_spreadsheet(excel_file, "Properties", ["Property"]),
        "Classes": read_spreadsheet(excel_file, "Classes", ["Class"]),
    }


@pytest.fixture(scope="session")
def david_rules(david_spreadsheet: dict[str, dict[str, Any]]) -> InformationRules:
    return InformationRules.model_validate(david_spreadsheet)
