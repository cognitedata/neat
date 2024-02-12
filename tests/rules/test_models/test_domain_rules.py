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
        "Properties": _read_spreadsheet(excel_file, "Properties"),
    }


@pytest.fixture(scope="session")
def emma_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-grid-emma.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": _read_spreadsheet(excel_file, "Properties", skiprows=1),
        "Classes": _read_spreadsheet(excel_file, "Classes", skiprows=1),
    }


def _read_spreadsheet(excel_file: pd.ExcelFile, sheet_name: str, skiprows: int = 0) -> list[Any]:
    return (
        pd.read_excel(excel_file, sheet_name, skiprows=skiprows)
        .dropna(axis=0, how="all")
        .replace(float("nan"), None)
        .to_dict(orient="records")
    )


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

        sample_expected_properties = {"WindTurbine.name", "WindFarm.windTurbine", "ExportCable.voltageLevel"}
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    def test_load_valid_emma_rules(self, emma_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DomainRules.model_validate(emma_spreadsheet)

        assert isinstance(valid_rules, DomainRules)

        sample_expected_properties = {"Substation.name", "Consumer.location", "Transmission.voltage"}
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property}" for prop in valid_rules.properties}

        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            DomainRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception
