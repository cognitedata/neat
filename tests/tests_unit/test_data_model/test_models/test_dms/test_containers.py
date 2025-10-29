from collections.abc import Callable, Iterator
from typing import Any, get_args

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    Constraint,
    ConstraintAdapter,
    ConstraintDefinition,
    ContainerRequest,
    ContainerResponse,
    DataType,
    DataTypeAdapter,
    EnumProperty,
    Index,
    IndexAdapter,
    IndexDefinition,
    InvertedIndex,
    PropertyTypeDefinition,
    UniquenessConstraintDefinition,
)
from cognite.neat._data_model.models.dms._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    ENUM_VALUE_IDENTIFIER_PATTERN,
    SPACE_FORMAT_PATTERN,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error

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
    @settings(max_examples=3)
    @given(data_type_strategy())
    def test_validate_data_types(self, data_type: dict[str, Any]) -> None:
        validated = DataTypeAdapter.validate_python(data_type)

        assert isinstance(validated, PropertyTypeDefinition)

        assert validated.model_dump(exclude_unset=True, by_alias=True) == data_type

    @pytest.mark.parametrize(
        "data,expected_errors",
        [
            pytest.param(
                {"type": "enum", "values": {"validValue1": {}, "invalid-value": {}}},
                {
                    "In enum.values enum value 'invalid-value' is not valid. Enum values must "
                    "match the pattern: ^[_A-Za-z][_0-9A-Za-z]{0,127}$."
                },
                id="Enum with invalid value key",
            ),
            pytest.param(
                {"type": "enum", "values": {}},
                {"In enum.values dictionary should have at least 1 item after validation, not 0."},
                id="Enum with empty values",
            ),
            pytest.param(
                {"type": "enum", "values": {"validValue1": {}}, "unknownValue": ""},
                {"In enum.unknownValue string should have at least 1 character."},
                id="Enum with empty unknownValue",
            ),
        ],
    )
    def test_parse_enum(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            DataTypeAdapter.validate_python(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors


class TestConstraint:
    @pytest.mark.parametrize(
        "data,expected_cls,expected_dump",
        [
            pytest.param(
                {
                    "constraintType": "uniqueness",
                    "properties": ["validProperty1", "validProperty_2"],
                    "bySpace": "True",
                },
                UniquenessConstraintDefinition,
                {
                    "constraintType": "uniqueness",
                    "properties": ["validProperty1", "validProperty_2"],
                    "bySpace": True,
                },
                id="Uniqueness constraint with bySpace as string",
            ),
            pytest.param(
                {
                    "constraintType": "uniqueness",
                    "properties": ["validProperty1"],
                },
                UniquenessConstraintDefinition,
                {
                    "bySpace": None,
                    "constraintType": "uniqueness",
                    "properties": ["validProperty1"],
                },
                id="Uniqueness constraint without bySpace (defaults to False)",
            ),
        ],
    )
    def test_parse_constraint(
        self, data: dict[str, Any], expected_cls: type[ConstraintDefinition], expected_dump: dict[str, Any]
    ) -> None:
        validated = ConstraintAdapter.validate_python(data)

        assert isinstance(validated, expected_cls)
        assert validated.model_dump(by_alias=True) == expected_dump


class TestIndex:
    @pytest.mark.parametrize(
        "data,expected_cls,expected_dump",
        [
            pytest.param(
                {
                    "indexType": "inverted",
                    "properties": ["validProperty1", "validProperty_2"],
                },
                InvertedIndex,
                {
                    "indexType": "inverted",
                    "properties": ["validProperty1", "validProperty_2"],
                },
                id="Inverted index with multiple properties",
            ),
            pytest.param(
                {"indexType": "btree", "properties": ["validProperty1"], "cursorable": None, "bySpace": "False"},
                BtreeIndex,
                {
                    "indexType": "btree",
                    "properties": ["validProperty1"],
                    "cursorable": None,
                    "bySpace": False,
                },
                id="Btree index with bySpace as string and cursorable as None",
            ),
        ],
    )
    def test_parse_index(
        self, data: dict[str, Any], expected_cls: type[IndexDefinition], expected_dump: dict[str, Any]
    ) -> None:
        validated = IndexAdapter.validate_python(data)

        assert isinstance(validated, expected_cls)
        assert validated.model_dump(by_alias=True) == expected_dump


def test_all_indices_are_in_union() -> None:
    all_indices = get_concrete_subclasses(IndexDefinition, exclude_direct_abc_inheritance=True)
    all_union_indices = get_args(Index.__args__[0])
    missing = set(all_indices) - set(all_union_indices)
    assert not missing, (
        f"The following IndexDefinition subclasses are "
        f"missing from the Index union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def test_all_constraints_are_in_union() -> None:
    all_constraints = get_concrete_subclasses(ConstraintDefinition, exclude_direct_abc_inheritance=True)
    all_union_constraints = get_args(Constraint.__args__[0])
    missing = set(all_constraints) - set(all_union_constraints)
    assert not missing, (
        f"The following ConstraintDefinition subclasses are "
        f"missing from the Constraint union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def test_all_property_types_are_in_union() -> None:
    all_property_types = get_concrete_subclasses(PropertyTypeDefinition, exclude_direct_abc_inheritance=True)
    all_union_property_types = get_args(DataType.__args__[0])
    missing = set(all_property_types) - set(all_union_property_types)
    assert not missing, (
        f"The following PropertyTypeDefinition subclasses are "
        f"missing from the DataType union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def invalid_container_definition_test_cases() -> Iterator:
    yield pytest.param(
        {"externalId": "MyContainer", "name": "way too long name" * 100, "usedFor": "not-instance", "properties": {}},
        {
            "In field 'name', string should have at most 255 characters.",
            "In field 'usedFor', input should be 'node', 'edge' or 'all'. Got 'not-instance'.",
            "Missing required field: 'space'.",
        },
        id="Multiple Issues. Missing required field, invalid name length, invalid value, and not properties",
    )

    # Test space validation
    yield pytest.param(
        {
            "space": "",
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'space', string should have at least 1 character."},
        id="Empty space field",
    )

    yield pytest.param(
        {
            "space": "a" * 44,  # Too long
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'space', string should have at most 43 characters."},
        id="Space too long",
    )

    yield pytest.param(
        {
            "space": "123invalid",  # Must start with letter
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'space', string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'."},
        id="Space invalid pattern - starts with number",
    )

    # Test external_id validation
    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "",
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'externalId', string should have at least 1 character."},
        id="Empty external_id",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "a" * 256,  # Too long
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'externalId', string should have at most 255 characters."},
        id="External_id too long",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "123invalid",  # Must start with letter
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'externalId', string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'."},
        id="External_id invalid pattern",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "String",  # Forbidden external ID
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {
            "In field 'externalId', 'String' is a reserved container External ID. "
            "Reserved External IDs are: Boolean, Date, File, Float, Float32, Float64, "
            "Int, Int32, Int64, JSONObject, Mutation, Numeric, PageInfo, Query, Sequence, "
            "String, Subscription, TimeSeries and Timestamp."
        },
        id="Forbidden external_id",
    )

    # Test description length
    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "description": "a" * 1025,  # Too long
            "properties": {"validProp": {"type": {"type": "text"}}},
        },
        {"In field 'description', string should have at most 1024 characters."},
        id="Description too long",
    )

    # Test property key validation
    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"space": {"type": {"type": "text"}}},  # Forbidden property key
        },
        {"In field 'properties', property keys cannot be any of the following reserved values: space."},
        id="Forbidden property key",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"invalid-key-!": {"type": {"type": "text"}}},  # Invalid pattern
        },
        {
            "In field 'properties', property keys must match pattern "
            "'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'. Invalid keys: "
            "invalid-key-!."
        },
        id="Invalid property key pattern",
    )

    # Test constraints validation
    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
            "constraints": {
                f"constraint{i}": {"constraintType": "uniqueness", "properties": ["validProp"]} for i in range(11)
            },  # Too many constraints
        },
        {"In field 'constraints', dictionary should have at most 10 items after validation, not 11."},
        id="Too many constraints",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
            "constraints": {
                "a" * 44: {"constraintType": "uniqueness", "properties": ["validProp"]}
            },  # Constraint key too long
        },
        {
            "In field 'constraints', constraints keys must be between 1 and 43 characters "
            "long. Invalid keys: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa."
        },
        id="Constraint key too long",
    )

    # Test indexes validation
    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
            "indexes": {
                f"index{i}": {"indexType": "btree", "properties": ["validProp"]} for i in range(11)
            },  # Too many indexes
        },
        {"In field 'indexes', dictionary should have at most 10 items after validation, not 11."},
        id="Too many indexes",
    )

    yield pytest.param(
        {
            "space": "validSpace",
            "externalId": "MyContainer",
            "properties": {"validProp": {"type": {"type": "text"}}},
            "indexes": {"a" * 44: {"indexType": "btree", "properties": ["validProp"]}},  # Index key too long
        },
        {
            "In field 'indexes', indexes keys must be between 1 and 43 characters long. "
            "Invalid keys: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa."
        },
        id="Index key too long",
    )


class TestContainerRequest:
    @pytest.mark.parametrize("data,expected_errors", list(invalid_container_definition_test_cases()))
    def test_invalid_container_definition(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            ContainerRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors
