from collections.abc import Iterable
from typing import Any

import pytest

from cognite.neat._data_model.models.dms import Filter, FilterAdapter


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


class TestViewFilters:
    @pytest.mark.parametrize("raw_data", list(view_filter_raw_data()))
    def test_roundtrip_serialization(self, raw_data: dict[str, Any]) -> None:
        loaded = FilterAdapter.validate_python(raw_data)
        assert isinstance(loaded, Filter)

        dumped = loaded.model_dump(by_alias=True, exclude_unset=True)
        assert dumped == raw_data
