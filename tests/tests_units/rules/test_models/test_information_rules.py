from datetime import datetime
from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules.information_rules import InformationRules
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL
from tests.tests_units.rules.test_models.utils import _read_spreadsheet


@pytest.fixture(scope="session")
def david_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "information-architect-david.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": _read_spreadsheet(excel_file, "Properties", skiprows=1),
        "Classes": _read_spreadsheet(excel_file, "Classes", skiprows=1),
    }


def invalid_domain_rules_cases():
    yield pytest.param(
        {
            "metadata": {
                "role": "information_architect",
                "creator": "Cognite",
                "contributor": "David",
                "prefix": "neat",
                "namespace": "http://www.neat.com",
                "version": "0.1.0",
                "created": datetime.utcnow(),
                "updated": datetime.utcnow(),
            },
            "properties": {},
        },
        "Value error, Metadata.role should be equal to 'information architect'",
        id="invalid_role",
    )
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "creator": "Jon, Emma",
                "contributor": "David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Rule Type": "rdfpath",
                    "Rule": None,
                }
            ],
        },
        (
            "Rule type 'rdfpath' provided for property 'name' in class 'GeneratingUnit' but rule is not provided!"
            "\nFor more information visit: "
            "https://cognite-neat.readthedocs-hosted.com/en/latest/api/exceptions.html#cognite.neat.rules.exceptions.RuleTypeProvidedButRuleMissing"
        ),
        id="missing_rule",
    )


class TestInformationRules:
    def test_load_valid_jon_rules(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = InformationRules.model_validate(david_spreadsheet)

        assert isinstance(valid_rules, InformationRules)

        sample_expected_properties = {
            "WindTurbine.manufacturer",
            "Substation.secondaryPowerLine",
            "WindFarm.exportCable",
        }
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            InformationRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception
