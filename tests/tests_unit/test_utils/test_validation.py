from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from cognite.neat._utils.validation import humanize_validation_error


class Person(BaseModel):
    name: str
    age: int


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
                },
                {"In row 2 at table 'People' the column 'Age' cannot be empty."},
                id="Missing required in table",
            )
        ],
    )
    def test_humanize_validation_error(
        self, data: dict[str, Any], args: dict[str, Any], expected_errors: set[str]
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Person.model_validate(data)

        errors = humanize_validation_error(exc_info.value, **args)
        assert set(errors) == expected_errors
