import pytest

from cognite.neat.rules import validation
from cognite.neat.rules.importers import DTDLImporter
from cognite.neat.rules.importers._dtdl2rules.spec import DTMI, Interface
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules.base import SchemaCompleteness
from cognite.neat.rules.validation import IssueList
from tests.tests_unit.rules.test_importers.constants import DTDL_IMPORTER_DATA


class TestDTDLImporter:
    def test_import_energy_grid_example(self) -> None:
        # In the example data, there is a property with an Object that does not have an identifier.
        # In addition, there is a class without properties
        expected_issues = IssueList(
            [
                validation.MissingIdentifier(component_type="Object"),
                validation.ClassNoPropertiesNoParents(["example_grid_transmission:baseReceiver(version=1)"]),
            ]
        )
        dtdl_importer = DTDLImporter.from_directory(DTDL_IMPORTER_DATA / "energy-grid")

        rules, issues = dtdl_importer.to_rules(errors="continue")

        assert issues == expected_issues
        assert isinstance(rules, InformationRules)

    def test_import_temperature_controller_example_dtdl_v2(self) -> None:
        expected_issues = IssueList(
            [
                validation.UnknownProperty(
                    component_type="Component",
                    property_name="schema",
                    instance_name="Device Information interface",
                    instance_id=None,
                ),
                validation.ImportIgnored(
                    reason="Neat does not have a concept of response for commands. This will be ignored.",
                    identifier="com_example:Thermostat(version=1).response",
                ),
            ]
        )
        dtdl_importer = DTDLImporter.from_zip(DTDL_IMPORTER_DATA / "TemperatureController.zip")

        rules, issues = dtdl_importer.to_rules(errors="continue")

        assert issues == expected_issues
        assert isinstance(rules, InformationRules)
        assert len(rules.classes) == 2

    def tests_import_invalid_data_model_and_return_errors(self) -> None:
        expected_issue = validation.DefaultPydanticError(
            type="IncompleteSchema",
            loc=(),
            msg="Classes {'com_example:TemperatureController(version=1)'} are not defined in the Class sheet!\n"
            "For more information visit: https://cognite-neat.readthedocs-hosted.com/en/latest/api/"
            "exceptions.html#cognite.neat.rules.exceptions.IncompleteSchema",
            input=None,
            ctx={
                "code": 28,
                "description": "This exceptions is raised when schema is not complete, meaning defined "
                "properties are pointing to non-existing classes or value types",
                "example": "",
                "fix": "",
                "type_": "IncompleteSchema",
            },
        )
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
            schema=SchemaCompleteness.complete,
        )

        rules, issues = dtdl_importer.to_rules(errors="continue")

        assert rules is None
        assert len(issues) == 1
        actual_issue = issues[0]
        assert isinstance(actual_issue, validation.DefaultPydanticError)
        # Setting the input to None, to avoid bloating the test with the large input
        # Using object.__setattr__ as errors are immutable
        object.__setattr__(actual_issue, "input", None)
        assert actual_issue == expected_issue


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
