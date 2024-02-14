from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules.dms_architect_rules import DMSRules
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL
from tests.tests_units.rules.test_models.utils import _read_spreadsheet


@pytest.fixture(scope="session")
def alice_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": _read_spreadsheet(excel_file, "Properties", skiprows=1),
        "Views": _read_spreadsheet(excel_file, "Views", skiprows=1),
        "Containers": _read_spreadsheet(excel_file, "Containers", skiprows=1),
    }


def invalid_dms_rules_cases():
    yield pytest.param(
        {"metadata": {"role": "information_architect"}, "properties": {}},
        "Value error, Metadata.role should be equal to 'DMS architect'",
        id="invalid_role",
    )


class TestDMSRules:
    def test_load_valid_alice_rules(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DMSRules.model_validate(alice_spreadsheet)

        assert isinstance(valid_rules, DMSRules)

        sample_expected_properties = {"WindTurbine.name", "WindFarm.windTurbine", "ExportCable.voltageLevel"}
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_dms_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            DMSRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception
