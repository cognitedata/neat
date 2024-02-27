from datetime import datetime
from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules import DMSRules
from cognite.neat.rules.models._rules.information_rules import InformationRules, _InformationRulesConverter
from cognite.neat.utils.spreadsheet import read_spreadsheet
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


@pytest.fixture(scope="session")
def david_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "information-architect-david.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_spreadsheet(excel_file, "Properties", ["Property"]),
        "Classes": read_spreadsheet(excel_file, "Classes", ["Class"]),
    }


def invalid_domain_rules_cases():
    # yield pytest.param(
    #         },
    #     },
    #     "Value error, Metadata.role should be equal to 'information architect'",
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
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


def incomplete_rules_case():
    # yield pytest.param(
    #         },
    #     },
    #     "Value error, Metadata.role should be equal to 'information architect'",
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
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
                    "Class": "GeneratingUnit2",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Rule Type": "rdfpath",
                    "Rule": "cim:GeneratingUnit",
                }
            ],
        },
        (
            "Classes {'GeneratingUnit2'} are not defined in the Class sheet!"
            "\nFor more information visit: "
            "https://cognite-neat.readthedocs-hosted.com/en/latest/api/exceptions.html#cognite.neat.rules.exceptions.IncompleteSchema"
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
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property_}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            InformationRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception

    @pytest.mark.parametrize("incomplete_rules, expected_exception", list(incomplete_rules_case()))
    def test_incomplete_rules(self, incomplete_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            InformationRules.model_validate(incomplete_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception

    def test_david_as_dms(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        david_rules = InformationRules.model_validate(david_spreadsheet)
        dms_rules = david_rules.as_dms_architect_rules()

        assert isinstance(dms_rules, DMSRules)


class TestInformationRulesConverter:
    @pytest.mark.parametrize(
        "prefix, expected_space",
        [
            pytest.param("neat", "neat", id="No substitutions"),
            pytest.param("my space", "my_space", id="Space with space character"),
            pytest.param("1my-space", "a1my-space", id="Space starting with number"),
            pytest.param("m" * 69, "m" * 43, id="Space with more than 43 characters"),
            pytest.param("my_space_", "my_space1", id="Space ending with underscore"),
        ],
    )
    def test_to_space(self, prefix: str, expected_space: str) -> None:
        actual_space = _InformationRulesConverter._to_space(prefix)

        assert actual_space == expected_space
