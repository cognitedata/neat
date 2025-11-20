from typing import cast

import pytest
from pydantic_core import ErrorDetails

from cognite.neat._data_model.importers._table_importer.source import TableSource
from cognite.neat._utils.validation import ValidationContext, as_json_path, humanize_validation_error


class TestHumanizeValidationError:
    @pytest.mark.parametrize(
        "error,context,expected_errors",
        [
            pytest.param(
                ErrorDetails(
                    **{
                        "type": "missing",
                        "loc": ("type", "enum", "values"),
                        "msg": "Field required",
                        "input": {"maxListSize": None, "list": False, "type": "enum"},
                    }
                ),
                ValidationContext(
                    parent_loc=("Properties", 276),
                    humanize_location=TableSource(source="dm.xlsx").location,
                    field_name="column",
                    field_renaming={"type": "Value Type"},
                    missing_required_descriptor="empty",
                ),
                (
                    "In table 'Properties' row 277 column 'Value Type' -> enum"
                    " definition is missing the collection reference."
                ),
                id="Missing enum collection reference in table",
            ),
            pytest.param(
                ErrorDetails(
                    type="missing",
                    loc=("age",),
                    msg="Field required",
                    input={"name": "Alice"},
                    url="https://errors.pydantic.dev/2.11/v/missing",
                ),
                ValidationContext(
                    parent_loc=("People", 1),
                    humanize_location=lambda loc: f"row {cast(int, loc[1]) + 1} at table {loc[0]!r}",
                    field_name="column",
                    field_renaming={"age": "Age"},
                    missing_required_descriptor="empty",
                ),
                "In row 2 at table 'People' the column 'Age' cannot be empty.",
                id="Missing required in table",
            ),
            pytest.param(
                ErrorDetails(
                    type="int_parsing",
                    loc=("age",),
                    msg="Input should be a valid integer, unable to parse string as an integer",
                    input="twenty",
                    url="https://errors.pydantic.dev/2.11/v/int_parsing",
                ),
                ValidationContext(),
                "In field 'age', input should be a valid integer, unable to parse string as an integer.",
                id="Type error with default formatting",
            ),
            pytest.param(
                ErrorDetails(
                    type="string_type",
                    loc=("name",),
                    msg="Input should be a valid string",
                    input=123,
                    url="https://errors.pydantic.dev/2.11/v/string_type",
                ),
                ValidationContext(field_name="value"),
                (
                    "In value 'name', input should be a valid string. Got 123 of type int. Hint: "
                    "Use double quotes to force string."
                ),
                id="String type error with custom field_name",
            ),
            pytest.param(
                ErrorDetails(
                    type="greater_than",
                    loc=("age",),
                    msg="Input should be greater than 0",
                    input=-5,
                    ctx={"gt": 0},
                    url="https://errors.pydantic.dev/2.11/v/greater_than",
                ),
                ValidationContext(
                    parent_loc=("Employees", 0),
                    humanize_location=lambda loc: f"employee {loc[1]} in {loc[0]}",
                ),
                "In employee 0 in Employees input should be greater than 0.",
                id="Custom location formatting",
            ),
            pytest.param(
                ErrorDetails(
                    type="missing",
                    loc=("age",),
                    msg="Field required",
                    input={"name": "Eve"},
                    url="https://errors.pydantic.dev/2.11/v/missing",
                ),
                ValidationContext(field_renaming={"name": "Full Name", "age": "Years Old"}),
                "Missing required field: 'age'.",
                id="Field renaming for error message",
            ),
            pytest.param(
                ErrorDetails(
                    type="int_parsing",
                    loc=("age",),
                    msg="Input should be a valid integer, unable to parse string as an integer",
                    input="fifty",
                    url="https://errors.pydantic.dev/2.11/v/int_parsing",
                ),
                ValidationContext(
                    parent_loc=("Data", 2),
                    humanize_location=lambda loc: f"at position {loc[1]} in {loc[0]}",
                    field_name="column",
                    field_renaming={"age": "Years"},
                ),
                "In at position 2 in Data input should be a valid integer, unable to parse string as an integer.",
                id="Combined custom parameters",
            ),
        ],
    )
    def test_humanize_validation_error(
        self, error: ErrorDetails, context: ValidationContext, expected_errors: str
    ) -> None:
        assert humanize_validation_error(error, context) == expected_errors


class TestAsJsonPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            (("data", 0, "attributes", "name"), "data[1].attributes.name"),
            (("items", 2, "details", 5, "value"), "items[3].details[6].value"),
            (("root", "level1", "level2", 3, "level3"), "root.level1.level2[4].level3"),
            (("a", "b-c", 1, "d.e", 0), "a.b-c[2].d.e[1]"),
            ((), ""),
        ],
    )
    def test_as_json_path(self, path: tuple[str | int, ...], expected: str) -> None:
        assert as_json_path(path) == expected
