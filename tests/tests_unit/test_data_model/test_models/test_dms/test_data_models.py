from collections.abc import Iterable
from typing import Any

import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import DataModelReference, DataModelRequest, DataModelResponse
from cognite.neat._utils.validation import humanize_validation_error

from .strategies import data_model_strategy


def invalid_data_model_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        {
            "externalId": "validExternalId",
            "version": "$invalidVersion",
            "views": [
                {"space": "valid_space", "externalId": "view1"},
                {"space": "valid_space", "externalId": "view2", "version": "@1"},
            ],
        },
        {
            "In field 'version', string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In views[1] missing required field: 'version'.",
            "In views[2].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "Missing required field: 'space'.",
        },
        id="Multiple errors in different fields",
    )
    yield pytest.param(
        {
            "space": "system",  # Forbidden space
            "externalId": "",  # Empty external ID (violates min_length=1)
            "version": "a" * 50,  # Too long version (max_length=43)
            "name": "x" * 300,  # Too long name (max_length=255)
            "description": "d" * 1100,  # Too long description (max_length=1024)
            "views": [
                {
                    "space": "1invalid",
                    "externalId": "Query",
                    "version": "v1",
                },  # Invalid space pattern and forbidden external_id
                {"space": "", "externalId": "valid_id", "version": ""},  # Empty space and version
            ],
        },
        {
            "In field 'description', string should have at most 1024 characters.",
            "In field 'externalId', string should have at least 1 character.",
            "In field 'name', string should have at most 255 characters.",
            "In field 'version', string should have at most 43 characters.",
            "In views[1].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
            "In views[2].space string should have at least 1 character.",
            "In views[2].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
        },
        id="Length violations, forbidden values, and pattern errors",
    )
    yield pytest.param(
        {
            "space": "a-space-name-that-is-way-too-long-and-exceeds-the-maximum-allowed-length",  # Too long space
            "externalId": "invalid@external#id",  # Invalid characters in external ID
            "version": "-invalid-start",  # Version starting with invalid character
            "views": [
                {},  # Missing all required fields
                {
                    "space": "space",
                    "externalId": "_invalid_start",
                    "version": "valid.version_1",
                },  # Forbidden space name, invalid external_id pattern
                {
                    "space": "valid_space",
                    "externalId": "valid_id",
                    "version": "invalid@version",
                },  # Invalid version pattern
            ],
        },
        {
            "In field 'externalId', string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In field 'space', string should have at most 43 characters.",
            "In field 'version', string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In views[1] missing required field: 'externalId'.",
            "In views[1] missing required field: 'space'.",
            "In views[1] missing required field: 'version'.",
            "In views[2].externalId string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In views[3].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
        },
        id="Boundary length errors, pattern violations, and missing required fields",
    )
    yield pytest.param(
        {
            "space": "cdf",  # Forbidden space name
            "externalId": "String",  # Forbidden external ID
            "version": "v",  # Valid minimal version
            "name": "",  # Empty name (allowed as it's optional with no min_length)
            "description": "",  # Empty description (allowed as it's optional with no min_length)
            "views": [
                {"space": "a", "externalId": "b", "version": "1"},  # Valid minimal view
                {
                    "space": "node",
                    "externalId": "Mutation",
                    "version": ".invalid",
                },  # Forbidden space and external_id, invalid version pattern
                {"space": "valid_space", "externalId": "a" * 256, "version": "valid1"},  # Too long external_id
            ],
        },
        {
            "In views[2].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In views[3].externalId string should have at most 255 characters.",
        },
        id="Forbidden values and edge cases with minimal valid fields",
    )
    yield pytest.param(
        {
            "space": "9invalid",  # Invalid space pattern (starts with number)
            "externalId": "1invalid",  # Invalid external_id pattern (starts with number)
            "version": "",  # Empty version (violates min_length constraint from regex)
            "name": None,  # Explicit None (should be allowed)
            "description": None,  # Explicit None (should be allowed)
            "views": [
                {
                    "space": "dms",
                    "externalId": "TimeSeries",
                    "version": "end-",
                },  # Forbidden space/external_id, invalid version ending
                {"space": "valid_space", "externalId": "valid_id", "version": "a" * 44},  # Too long version
                {
                    "space": "_invalid",
                    "externalId": "valid_id",
                    "version": "valid1",
                },  # Invalid space pattern (starts with underscore)
                {"space": "valid_space", "externalId": "valid_id", "version": "1.2.3-beta_1"},  # Valid complex version
            ],
        },
        {
            "In field 'externalId', string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In field 'space', string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
            "In field 'version', string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In views[1].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In views[2].version string should have at most 43 characters.",
            "In views[3].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
        },
        id="Pattern validation failures and complex nested errors",
    )


class TestDataModelRequest:
    @pytest.mark.parametrize("data,expected_errors", list(invalid_data_model_test_cases()))
    def test_invalid_definitions(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            DataModelRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors


class TestDataModelResponse:
    @settings(max_examples=1)
    @given(data_model_strategy())
    def test_as_request(self, data_model: dict[str, Any]) -> None:
        response = DataModelResponse.model_validate(data_model)

        assert isinstance(response, DataModelResponse)

        request = response.as_request()
        assert isinstance(request, DataModelRequest)

        reference = response.as_reference()
        assert isinstance(reference, DataModelReference)

        dumped = request.model_dump()
        response_dumped = response.model_dump()
        response_only_keys = set(DataModelResponse.model_fields.keys()) - set(DataModelRequest.model_fields.keys())
        for keys in response_only_keys:
            response_dumped.pop(keys, None)
        assert dumped == response_dumped
