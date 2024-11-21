import pytest

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import ResourceMissingIdentifierError, ResourceNotDefinedError
from cognite.neat._issues.warnings import PropertyTypeNotSupportedWarning, ResourceTypeNotSupportedWarning
from cognite.neat._rules.importers import DTDLImporter
from cognite.neat._rules.importers._dtdl2rules.spec import DTMI, Interface
from cognite.neat._rules.models import InformationRules
from cognite.neat._rules.transformers import ImporterPipeline
from tests.tests_unit.rules.test_importers.constants import DTDL_IMPORTER_DATA


class TestDTDLImporter:
    def test_import_energy_grid_example(self) -> None:
        # In the example data, there is a property with an Object that does not have an identifier.
        expected_issues = IssueList([ResourceMissingIdentifierError("Object")])
        dtdl_importer = DTDLImporter.from_directory(DTDL_IMPORTER_DATA / "energy-grid")

        result = ImporterPipeline.try_verify(dtdl_importer)
        rules, issues = result.rules, result.issues

        assert issues == expected_issues
        assert isinstance(rules, InformationRules)

    def test_import_temperature_controller_example_dtdl_v2(self) -> None:
        expected_issues = IssueList(
            [
                PropertyTypeNotSupportedWarning(
                    "Device Information interface",
                    "Component",
                    "schema",
                    "missing",
                ),
                ResourceTypeNotSupportedWarning("com_example:Thermostat(version=1).response", "Command.Response"),
            ]
        )
        dtdl_importer = DTDLImporter.from_zip(DTDL_IMPORTER_DATA / "TemperatureController.zip")

        result = ImporterPipeline.try_verify(dtdl_importer)
        rules, issues = result.rules, result.issues

        assert issues == expected_issues
        assert isinstance(rules, InformationRules)
        assert len(rules.classes) == 2

    def tests_import_invalid_data_model_and_return_errors(self) -> None:
        dtdl_importer = DTDLImporter(
            [
                Interface.model_validate(
                    {
                        "@context": "dtmi:dtdl:context;3",
                        "@id": "dtmi:com:example:Thermostat;1",
                        "displayName": "Thermostat",
                        "extends": ["dtmi:com:example:TemperatureController;1"],
                        "contents": [],
                    }
                )
            ],
        )

        result = ImporterPipeline.try_verify(dtdl_importer)
        rules, issues = result.rules, result.issues

        assert rules is None
        assert len(issues) == 1
        actual_issue = issues[0]
        assert isinstance(actual_issue, ResourceNotDefinedError)


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
