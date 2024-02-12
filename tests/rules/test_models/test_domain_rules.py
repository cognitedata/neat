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


def invalid_domain_rules_cases():
    yield pytest.param(
        {"metadata": {"role": "information_architect", "creator": "Cognite"}, "properties": {}},
        "Value error, Metadata.role should be equal to 'domain expert'",
        id="invalid_role",
    )

    yield pytest.param(
        {"metadata": {"creator": "Cognite"}, "properties": {}},
        "Value error, Metadata.role is missing.",
        id="Missing role",
    )

    yield pytest.param(
        {"metadata": {"role": "domain expert"}, "properties": {}},
        "Field required",
        id="Missing creator",
    )


class TestDomainRules:
    def test_load_valid_jon_rules(self, jon_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DomainRules.model_validate(jon_spreadsheet)

        assert isinstance(valid_rules, DomainRules)

    def test_load_valid_emma_rules(self, emma_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DomainRules.model_validate(emma_spreadsheet)

        assert isinstance(valid_rules, DomainRules)

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            DomainRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception
