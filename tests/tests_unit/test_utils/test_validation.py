from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from cognite.neat._utils.validation import humanize_validation_error


class Person(BaseModel):
    name: str
    age: int = Field(..., gt=0)


class TestHumanizeValidationError:
    @pytest.mark.parametrize(
        "data,args,expected_errors",
        [
            pytest.param(
                {"name": "Alice"},
                {
                    "parent_loc": ("People", 1),
                    "humanize_location": lambda loc: f"row {loc[1] + 1} at table {loc[0]!r}",
                    "field_name": "column",
                    "field_renaming": {"age": "Age"},
                    "missing_required": "empty",
                },
                {"In row 2 at table 'People' the column 'Age' cannot be empty."},
                id="Missing required in table",
            ),
            pytest.param(
                {"name": "Bob", "age": "twenty"},
                {},
                {"In field age input should be a valid integer, unable to parse string as an integer"},
                id="Type error with default formatting",
            ),
            pytest.param(
                {"name": 123, "age": 40},
                {"field_name": "value"},
                {
                    "In value name input should be a valid string. Got 123 of type int. Hint: Use "
                    "double quotes to force string."
                },
                id="String type error with custom field_name",
            ),
            pytest.param(
                {"name": "Dave", "age": -5},
                {
                    "parent_loc": ("Employees", 0),
                    "humanize_location": lambda loc: f"employee {loc[1]} in {loc[0]}",
                },
                {"In employee 0 in Employees input should be greater than 0"},
                id="Custom location formatting",
            ),
            pytest.param(
                {"name": "Eve"},
                {"field_renaming": {"name": "Full Name", "age": "Years Old"}},
                {"Missing required field: 'age'"},
                id="Field renaming for error message",
            ),
            pytest.param(
                {"name": "Frank", "age": "fifty"},
                {
                    "parent_loc": ("Data", 2),
                    "humanize_location": lambda loc: f"at position {loc[1]} in {loc[0]}",
                    "field_name": "column",
                    "field_renaming": {"age": "Years"},
                },
                {"In at position 2 in Data input should be a valid integer, unable to parse string as an integer"},
                id="Combined custom parameters",
            ),
        ],
    )
    def test_humanize_validation_error(
        self, data: dict[str, Any], args: dict[str, Any], expected_errors: set[str]
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Person.model_validate(data)

        errors = humanize_validation_error(exc_info.value, **args)
        assert set(errors) == expected_errors
