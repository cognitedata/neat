from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import SpaceRequest
from cognite.neat._utils.validation import humanize_validation_error


def invalid_space_definition_test_cases() -> Iterator[tuple]:
    yield pytest.param(
        {"space": "my_space", "name": "way too long name" * 50},
        {
            "In field name string should have at most 255 characters",
        },
        id="Name above 255 characters",
    )


class TestSpaceRequest:
    @pytest.mark.parametrize("data,expected_errors", list(invalid_space_definition_test_cases()))
    def test_invalid_definition(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            SpaceRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors
