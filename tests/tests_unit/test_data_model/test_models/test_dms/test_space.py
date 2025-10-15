from collections.abc import Callable, Iterator
from typing import Any

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import SpaceRequest, SpaceResponse
from cognite.neat._data_model.models.dms._constants import SPACE_FORMAT_PATTERN
from cognite.neat._utils.validation import humanize_validation_error


def invalid_space_definition_test_cases() -> Iterator[tuple]:
    yield pytest.param(
        {"space": "my_space", "name": "way too long name" * 50},
        {"In field 'name', string should have at most 255 characters."},
        id="Name above 255 characters",
    )
    yield pytest.param(
        {"space": "forbidden#space", "name": "Valid Name", "description": "Way too long description" * 100},
        {
            "In field 'description', string should have at most 1024 characters.",
            "In field 'space', string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
        },
        id="Forbidden space and description above 1024 characters",
    )


@st.composite
def space_strategy(draw: Callable) -> dict[str, Any]:
    return dict(
        space=draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        name=draw(st.text(min_size=1, max_size=255)),
        description=draw(st.text(min_size=0, max_size=1024)),
        isGlobal=draw(st.booleans()),
        createdTime=draw(st.integers(min_value=0)),
        lastUpdatedTime=draw(st.integers(min_value=0)),
    )


class TestSpaceRequest:
    @settings(max_examples=1)
    @given(space_strategy())
    def test_space_as_request(self, space_data: dict[str, Any]) -> None:
        space_response = SpaceResponse.model_validate(space_data)
        request = space_response.as_request()
        assert request.space == space_response.space
        assert request.name == space_response.name
        assert request.description == space_response.description

    @pytest.mark.parametrize("data,expected_errors", list(invalid_space_definition_test_cases()))
    def test_invalid_definition(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            SpaceRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors
