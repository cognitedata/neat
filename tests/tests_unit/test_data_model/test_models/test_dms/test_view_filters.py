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


class TestViewFilters:
    @pytest.mark.parametrize("raw_data", list(view_filter_raw_data()))
    def test_roundtrip_serialization(self, raw_data: dict[str, Any]) -> None:
        loaded = FilterAdapter.validate_python(raw_data)
        assert isinstance(loaded, Filter)

        dumped = loaded.model_dump(by_alias=True, exclude_unset=True)
        assert dumped == raw_data
