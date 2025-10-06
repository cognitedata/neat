from collections.abc import Callable
from typing import Any

import hypothesis.strategies as st
from hypothesis import given, settings

from cognite.neat._data_model.models.dms import SpaceResponse
from cognite.neat._data_model.models.dms._constants import SPACE_FORMAT_PATTERN


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
