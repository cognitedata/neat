from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules.domain_rules import DomainRules
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


@pytest.fixture(scope="session")
def jon_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-wind-energy-jon.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": pd.read_excel(excel_file, "Properties").to_dict(orient="dict"),
    }


@pytest.fixture(scope="session")
def emma_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-grid-emma.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": pd.read_excel(excel_file, "Properties").to_dict(orient="dict"),
        "Classes": pd.read_excel(excel_file, "Classes").to_dict(orient="dict"),
    }


class TestDomainRules:
    def test_load_valid_jon_rules(self, jon_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DomainRules.model_validate(jon_spreadsheet)

        assert isinstance(valid_rules, DomainRules)

    def test_load_valid_emma_rules(self, emma_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DomainRules.model_validate(emma_spreadsheet)

        assert isinstance(valid_rules, DomainRules)
