from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._exceptions import ModelImportError
from cognite.neat._utils.useful_types import CellValue


def invalid_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": [
                {
                    "Name": "space",
                    "Value": "my_space",
                }
            ],
            "properties": [
                {
                    "View": "MyView",
                    "View Property": "prop1",
                    "Value Type": "text",
                    "Min Count": 1,
                    "Max Count": 1,
                },
                {
                    "View": "asset:MyAsset(capacity=100,type=storage)trailing",
                    "View Property": "prop2",
                    "Value Type": "int32",
                    "Min Count": "not_an_int",
                    "Max Count": 1,
                },
            ],
        },
        {
            "In Properties sheet missing required column: 'Connection'.",
            "In Properties sheet row 2 column 'Min Count' input should be a valid "
            "integer, unable to parse string as an integer.",
            "In Properties sheet row 2 column 'View' invalid entity syntax: Unexpected "
            "characters after properties at position 40. Got 't'.",
            "Missing required column: 'Views'.",
        },
        id="Missing required column in Properties table",
    )

    yield pytest.param(
        {
            "Metadata": [
                {
                    "Name": "space",
                    "Value": "my_space",
                }
            ],
            "Properties": [
                {
                    "View": "MyView",
                    "View Property": "prop1",
                    "Value Type": "text",
                    "Connection": "MyConnection",
                    "Immutable": "not_a_boolean",
                    "Auto Increment": "maybe",
                }
            ],
            "Views": [
                {
                    "View": "MyView",
                    "Implements": "invalid[entity,list]syntax",
                    "In Model": "yes_but_not_boolean",
                }
            ],
        },
        {
            "In Properties sheet missing required column: 'Max Count'.",
            "In Properties sheet missing required column: 'Min Count'.",
            "In Properties sheet row 1 column 'Auto Increment' input should be a valid "
            "boolean, unable to interpret input.",
            "In Properties sheet row 1 column 'Immutable' input should be a valid boolean, unable to interpret input.",
            "In Views sheet row 1 column 'In Model' input should be a valid boolean, unable to interpret input.",
        },
        id="Invalid boolean and entity list values",
    )

    yield pytest.param(
        {
            "Metadata": [
                {
                    "Value": "my_space",  # Missing required "Name" field
                }
            ],
            "Properties": [
                {
                    "View": "MyView",
                    "Value Type": "text",  # Missing required "View Property" field
                    "Connection": "MyConnection",
                }
            ],
            "Views": [
                {
                    # Missing required "View" field entirely
                    "Name": "Some View Name",
                }
            ],
        },
        {
            "In Metadata sheet missing required column: 'Name'.",
            "In Properties sheet missing required column: 'Max Count'.",
            "In Properties sheet missing required column: 'Min Count'.",
            "In Properties sheet missing required column: 'View Property'.",
            "In Views sheet missing required column: 'View'.",
        },
        id="Missing required fields in various sheets",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data, expected_errors", list(invalid_test_cases()))
    def test_read_invalid_tables(self, data: dict[str, list[dict[str, CellValue]]], expected_errors: set[str]) -> None:
        importer = DMSTableImporter(data)
        with pytest.raises(ModelImportError) as exc_info:
            importer._read_tables()
        actual_errors = {err.message for err in exc_info.value.errors}
        assert actual_errors == expected_errors
