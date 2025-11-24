from collections.abc import Iterable
from typing import Any

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import FilterAdapter
from cognite.neat._data_model.models.dms._view_filter import AVAILABLE_FILTERS, FilterDataDefinition
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.validation import humanize_validation_error


def view_filter_raw_data() -> Iterable[tuple]:
    yield pytest.param(
        {"equals": {"property": ["node", "space"], "value": "my_space"}},
        id="equals_filter",
    )
    yield pytest.param(
        {
            "and": [
                {"exists": {"property": ["node", "externalId"]}},
                {"prefix": {"property": ["node", "viewId/v1", "category"], "value": "Sensor"}},
            ]
        },
        id="and_filter",
    )
    yield pytest.param(
        {
            "or": [
                {"equals": {"property": ["node", "space"], "value": "space1"}},
                {"equals": {"property": ["node", "space"], "value": "space2"}},
            ]
        },
        id="or_filter",
    )
    yield pytest.param(
        {"not": {"equals": {"property": ["node", "space"], "value": "excluded_space"}}},
        id="not_filter",
    )
    yield pytest.param(
        {"prefix": {"property": ["node", "viewId/v1", "name"], "value": "test"}},
        id="prefix_filter",
    )
    yield pytest.param(
        {"in": {"property": ["node", "space"], "values": ["space1", "space2", "space3"]}},
        id="in_filter",
    )
    yield pytest.param(
        {
            "range": {
                "property": ["node", "viewId/v1", "temperature"],
                "gte": 20.0,
                "lt": 30.0,
            }
        },
        id="range_filter",
    )
    yield pytest.param(
        {"exists": {"property": ["node", "externalId"]}},
        id="exists_filter",
    )
    yield pytest.param(
        {
            "containsAny": {
                "property": ["node", "viewId/v1", "tags"],
                "values": ["tag1", "tag2", "tag3"],
            }
        },
        id="contains_any_filter",
    )
    yield pytest.param(
        {
            "containsAll": {
                "property": ["node", "viewId/v1", "requiredTags"],
                "values": ["required1", "required2"],
            }
        },
        id="contains_all_filter",
    )
    yield pytest.param(
        {"matchAll": {}},
        id="match_all_filter",
    )
    yield pytest.param(
        {
            "nested": {
                "property": ["edge", "endNode"],
                "scope": ["node"],
                "filter": {"equals": {"property": ["node", "space"], "value": "my_space"}},
            }
        },
        id="nested_filter",
    )
    yield pytest.param(
        {
            "overlaps": {
                "property": ["node", "viewId/v1", "timeseries"],
                "startProperty": ["node", "viewId/v1", "startTime"],
                "endProperty": ["node", "viewId/v1", "endTime"],
                "gte": "2023-01-01T00:00:00Z",
                "lt": "2024-01-01T00:00:00Z",
            }
        },
        id="overlaps_filter",
    )
    yield pytest.param(
        {
            "hasData": [
                {"space": "my_space", "externalId": "MyView", "version": "v1", "type": "view"},
                {"space": "my_space", "externalId": "MyContainer", "type": "container"},
            ]
        },
        id="has_data_filter",
    )
    yield pytest.param(
        {
            "instanceReferences": [
                {"space": "my_space", "externalId": "node1"},
                {"space": "my_space", "externalId": "node2"},
            ]
        },
        id="instance_references_filter",
    )


class TestViewFilters:
    @pytest.mark.parametrize("raw_data", list(view_filter_raw_data()))
    def test_roundtrip_serialization(self, raw_data: dict[str, Any]) -> None:
        loaded = FilterAdapter.validate_python(raw_data)
        assert isinstance(loaded, dict)

        dumped = FilterAdapter.dump_python(loaded, by_alias=True, exclude_unset=True)
        assert dumped == raw_data

    @pytest.mark.parametrize(
        "raw_data, expected_error_msg",
        [
            pytest.param(
                {"equals": {"property": ["node", "space"]}},
                "In equals.equals missing required field: 'value'.",
                id="missing_value_in_equals_filter",
            ),
            pytest.param(
                {"in": {"property": ["node", "space"], "values": "not-a-list"}},
                "Input must be a list. Got 'not-a-list' of type str.",
                id="invalid_values_type_in_in_filter",
            ),
            pytest.param(
                {"unknownFilterType": {"property": ["node", "space"], "value": "my_space"}},
                (
                    "Unknown filter type: 'unknownFilterType'. Available filter types: and, "
                    "containsAll, containsAny, equals, exists, hasData, in, instanceReferences, "
                    "matchAll, nested, not, or, overlaps, prefix and range."
                ),
                id="unknown_filter_type",
            ),
        ],
    )
    def test_validation_errors(self, raw_data: dict[str, Any], expected_error_msg: str) -> None:
        try:
            FilterAdapter.validate_python(raw_data)
        except ValidationError as e:
            errors = e.errors()
            assert len(errors) == 1
            error_msg = humanize_validation_error(errors[0])
            assert error_msg == expected_error_msg
        else:
            raise AssertionError("ValidationError was expected but not raised.")

    def test_filter_data_for_all_filter_types(self) -> None:
        filter_data_types = {
            subclass.model_fields["filter_type"].default for subclass in get_concrete_subclasses(FilterDataDefinition)
        }
        assert filter_data_types == AVAILABLE_FILTERS
