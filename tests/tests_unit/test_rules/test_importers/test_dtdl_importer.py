import pytest

from cognite.neat.core._issues import IssueList, catch_issues
from cognite.neat.core._issues.errors import (
    ResourceMissingIdentifierError,
    ResourceNotDefinedError,
)
from cognite.neat.core._issues.warnings import (
    PropertyTypeNotSupportedWarning,
    ResourceTypeNotSupportedWarning,
)
from cognite.neat.core._rules.importers import DTDLImporter
from cognite.neat.core._rules.importers._dtdl2rules.spec import DTMI, Interface
from cognite.neat.core._rules.models import InformationRules
from cognite.neat.core._rules.transformers import VerifyInformationRules
from tests.data import SchemaData


class TestDTDLImporter:
    def test_import_energy_grid_example(self) -> None:
        # In the example data, there is a property with an Object that does not have an identifier.
        expected_issues = IssueList([ResourceMissingIdentifierError("Object")])

        with catch_issues() as issues:
            read_rules = DTDLImporter.from_directory(SchemaData.NonNeatFormats.DTDL.energy_grid).to_rules()
            _ = VerifyInformationRules().transform(read_rules)

        assert issues == expected_issues

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
        with catch_issues() as issues:
            read_rules = DTDLImporter.from_zip(SchemaData.NonNeatFormats.DTDL.temperature_controller).to_rules()
            rules = VerifyInformationRules().transform(read_rules)

        assert issues == expected_issues
        assert isinstance(rules, InformationRules)
        assert len(rules.classes) == 2

    @pytest.mark.skip("Will be fixed in separate PR")
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

        read_rules = dtdl_importer.to_rules()
        with catch_issues() as issues:
            rules = VerifyInformationRules().transform(read_rules)

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
