import pytest

from cognite.neat.rules import validation
from cognite.neat.rules.importers import DTDLImporter
from cognite.neat.rules.importers._dtdl2rules._v3_spec import DTMI
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.validation import IssueList
from tests.tests_unit.rules.test_importers.constants import DTDL_IMPORTER_DATA


class TestDTDLImporter:
    def test_import_energy_grid_example(self) -> None:
        # In the example data, there is a property with an Object that does not have an identifier.
        expected_issues = IssueList([validation.MissingIdentifier(component_type="Object")])
        dtdl_importer = DTDLImporter.from_directory(DTDL_IMPORTER_DATA / "energy-grid")

        rules, issues = dtdl_importer.to_rules(errors="continue")

        assert isinstance(rules, InformationRules)
        assert issues == expected_issues

    def tests_import_invalid_data_model_and_return_errors(self) -> None:
        expected_issues = []
        dtdl_importer = DTDLImporter([])

        rules, issues = dtdl_importer.to_rules(errors="continue")

        assert rules is None
        assert sorted(issues) == sorted(expected_issues)


class TestV3Spec:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("dtmi:com:example:Thermostat;1", DTMI(path=["com", "example", "Thermostat"], version="1")),
            ("dtmi:foo_bar:_16:baz33:qux;12", DTMI(path=["foo_bar", "_16", "baz33", "qux"], version="12")),
        ],
    )
    def test_DTMI_from_string(self, raw: str, expected: DTMI) -> None:
        actual = DTMI.model_validate(raw)

        assert actual == expected

        assert raw == actual.model_dump()
