from collections.abc import Iterator
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import (
    ViewPropertyDefinition,
    ViewRequest,
    ViewRequestProperty,
    ViewResponseProperty,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error


def test_all_view_properties_are_in_union() -> None:
    all_property_classes = get_concrete_subclasses(ViewPropertyDefinition, exclude_direct_abc_inheritance=True)
    response_union = get_args(ViewResponseProperty.__args__[0])
    request_union = get_args(ViewRequestProperty.__args__[0])
    all_properties_union = set(response_union).union(set(request_union))
    missing = set(all_property_classes) - set(all_properties_union)
    assert not missing, (
        f"The following ViewPropertyDefinitions subclasses are "
        f"missing from the ViewPropertyDefinitions union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def invalid_view_definition_test_cases() -> Iterator[tuple]:
    yield pytest.param(
        {
            "externalId": "MyView",
            "name": "way too long name" * 100,
            "version": "#NotValid",
            "implements": [{"space": "*my_invalid_space", "externalId": "MyParent"}],
            "properties": {
                "invalid-name": {
                    "container": {"space": "my_space", "externalId": "MyContainer"},
                    "containerPropertyIdentifier": "containerProperty",
                },
                "valid_name": {
                    "connectionType": "single_edge_connection",
                    "source": {"space": "my_space", "externalId": "MySourceView", "version": "1"},
                    "type": {"space": "my_space", "externalId": "MyNode"},
                    "direction": "sideways",
                },
            },
        },
        {
            "Missing required field: 'space'",
            "In field name string should have at most 255 characters",
            "In field version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'",
            "In implements[1] missing required field: 'version'",
            "In implements[1].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'",
            "In properties.valid_name.single_edge_connection.direction input should be 'outwards' or 'inwards'. "
            "Got 'sideways'.",
        },
        id="Multiple Issues.",
    )


class TestViewRequests:
    @pytest.mark.parametrize("data,expected_errors", list(invalid_view_definition_test_cases()))
    def test_invalid_container_definition(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            ViewRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors
