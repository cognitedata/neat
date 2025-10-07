from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._exceptions import ModelImportError
from cognite.neat._utils.useful_types import CellValue


def invalid_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": [
                {
                    "Name": "space",
                    "Value": "my_space",
                }
            ],
            "Properties": [
                {
                    "View": "MyView",
                    "View Property": "prop1",
                    "Value Type": "text",
                    "Min Count": 1,
                    "Max Count": 1,
                },
                {
                    "View": "MyView",
                    "View Property": "prop2",
                    "Value Type": "number",
                    "Min Count": 0,
                    "Max Count": 1,
                },
            ],
            "Views": [
                {
                    "View": "ValidView",
                    "Name": "A valid view",
                }
            ],
        },
        {"In Properties sheet missing required column: 'Connection'"},
        id="Missing required column in Properties table",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data, expected_errors", list(invalid_test_cases()))
    def test_read_invalid_tables(self, data: dict[str, list[dict[str, CellValue]]], expected_errors: set[str]) -> None:
        importer = DMSTableImporter(data)
        with pytest.raises(ModelImportError) as exc_info:
            importer._read_tables()
        actual_errors = {err.message for err in exc_info.value.errors}
        assert actual_errors == expected_errors
