from collections.abc import Iterator
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import (
    Constraint,
    ConstraintDefinition,
    ContainerRequest,
    DataType,
    Index,
    IndexDefinition,
    PropertyTypeDefinition,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error


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
            "In field 'properties', dictionary should have at least 1 item after validation, not 0.",
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
