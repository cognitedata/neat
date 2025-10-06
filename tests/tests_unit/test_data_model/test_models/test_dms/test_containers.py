from collections.abc import Callable
from typing import Any

import hypothesis.strategies as st
from hypothesis import given, settings

from cognite.neat._data_model.models.dms import (
    ContainerRequest,
    ContainerResponse,
    DataTypeAdapter,
    EnumProperty,
    PropertyTypeDefinition,
)
from cognite.neat._data_model.models.dms._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    ENUM_VALUE_IDENTIFIER_PATTERN,
    SPACE_FORMAT_PATTERN,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses

DATA_TYPE_CLS_BY_TYPE = {
    # Skipping enum as it requires special handling
    subclass.model_fields["type"].default: subclass
    for subclass in get_concrete_subclasses(PropertyTypeDefinition)
    if subclass is not EnumProperty
}


@st.composite
def data_type_strategy(draw: Callable) -> dict[str, Any]:
    # Generate property keys matching the pattern
    type_ = draw(st.sampled_from(list(DATA_TYPE_CLS_BY_TYPE.keys())))
    if type_ == "enum":
        enum_values = draw(
            st.lists(
                st.from_regex(ENUM_VALUE_IDENTIFIER_PATTERN, fullmatch=True),
                min_size=1,
                max_size=12,
                unique=True,
            )
        )
        return {
            "type": type_,
            "values": {
                key: {
                    "name": draw(st.one_of(st.none(), st.text(min_size=1, max_size=255))),
                    "description": draw(st.one_of(st.none(), st.text(max_size=1024))),
                }
                for key in enum_values
            },
            "unknownValue": draw(st.one_of(st.none(), st.text(min_size=1, max_size=255))),
        }
    else:
        return {
            "type": type_,
            "list": draw(st.one_of(st.none(), st.booleans())),
            "maxListSize": draw(st.one_of(st.none(), st.integers(min_value=1, max_value=2000))),
        }


@st.composite
def container_property_definition_strategy(draw: Callable) -> dict[str, Any]:
    return dict(
        immutable=draw(st.booleans()),
        nullable=draw(st.booleans()),
        autoIncrement=draw(st.booleans()),
        defaultValue=draw(
            st.one_of(st.none(), st.text(), st.integers(), st.booleans(), st.dictionaries(st.text(), st.integers()))
        ),
        description=draw(st.one_of(st.none(), st.text(max_size=1024))),
        name=draw(st.one_of(st.none(), st.text(max_size=255))),
        type=draw(data_type_strategy()),
    )


@st.composite
def container_strategy(draw: Callable) -> dict[str, Any]:
    # Generate property keys matching the pattern
    prop_keys = draw(
        st.lists(
            st.from_regex(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN, fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    properties = {k: draw(container_property_definition_strategy()) for k in prop_keys}
    return dict(
        space=draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        externalId=draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
        name=draw(st.one_of(st.none(), st.text(max_size=255))),
        description=draw(st.one_of(st.none(), st.text(max_size=1024))),
        usedFor=draw(st.one_of(st.none(), st.sampled_from(["node", "edge", "all"]))),
        properties=properties,
        isGlobal=draw(st.booleans()),
        createdTime=draw(st.integers(min_value=0)),
        lastUpdatedTime=draw(st.integers(min_value=0)),
    )


class TestContainerResponse:
    @settings(max_examples=1)
    @given(container_strategy())
    def test_as_request(self, container: dict[str, Any]) -> None:
        container_instance = ContainerResponse.model_validate(container)

        request = container_instance.as_request()

        assert isinstance(request, ContainerRequest)

        dumped = request.model_dump()
        response_dumped = container_instance.model_dump()
        response_only_keys = set(ContainerResponse.model_fields.keys()) - set(ContainerRequest.model_fields.keys())
        for keys in response_only_keys:
            response_dumped.pop(keys, None)
        assert dumped == response_dumped


class TestDataTypeAdapter:
    @settings(max_examples=10)
    @given(data_type_strategy())
    def test_enum_values(self, data_type: dict[str, Any]) -> None:
        validated = DataTypeAdapter.validate_python(data_type)

        assert isinstance(validated, PropertyTypeDefinition)

        assert validated.model_dump(exclude_unset=True, by_alias=True) == data_type
