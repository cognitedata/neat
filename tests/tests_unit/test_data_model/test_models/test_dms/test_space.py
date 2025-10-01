import hypothesis.strategies as st
from hypothesis import given

from cognite.neat._data_model.models.dms import SpaceResponse
from cognite.neat._data_model.models.dms._constants import SPACE_FORMAT_PATTERN


@st.composite
def space_strategy(draw) -> SpaceResponse:
    return SpaceResponse(
        space=draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        name=draw(st.text(min_size=1, max_size=255)),
        description=draw(st.text(min_size=0, max_size=1024)),
        isGlobal=draw(st.booleans()),
        createdTime=draw(st.integers(min_value=0)),
        lastUpdatedTime=draw(st.integers(min_value=0)),
    )


class TestSpaceRequest:
    @given(space_strategy())
    def test_space_as_request(self, space_response: SpaceResponse) -> None:
        request = space_response.as_request()
        assert request.space == space_response.space
        assert request.name == space_response.name
        assert request.description == space_response.description
