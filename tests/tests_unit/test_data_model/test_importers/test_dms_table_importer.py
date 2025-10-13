from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.importers._table_importer.source import SpreadsheetReadContext, TableSource
from cognite.neat._exceptions import DataModelImportError
from cognite.neat._utils.useful_types import CellValueType


def invalid_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": [
                {
                    "Key": "space",
                    "Value": "my_space",
                }
            ],
            "properties": [
                {
                    "View": "MyView",
                    "View Property": "prop1",
                    "Value Type": "text",
                    "Min Count": 1,
                    "Max Count": 1,
                },
                {
                    "View": "asset:MyAsset(capacity=100,type=storage)trailing",
                    "View Property": "prop2",
                    "Value Type": "int32",
                    "Min Count": "not_an_int",
                    "Max Count": 1,
                },
            ],
        },
        {
            "In Properties sheet missing required column: 'Connection'.",
            "In Properties sheet row 2 column 'Min Count' input should be a valid "
            "integer, unable to parse string as an integer.",
            "In Properties sheet row 2 column 'View' invalid entity syntax: Unexpected "
            "characters after properties at position 40. Got 't'.",
            "Missing required column: 'Views'.",
        },
        id="Missing required column in Properties table",
    )

    yield pytest.param(
        {
            "Metadata": [
                {
                    "Key": "space",
                    "Value": "my_space",
                }
            ],
            "Properties": [
                {
                    "View": "MyView",
                    "View Property": "prop1",
                    "Value Type": "text",
                    "Connection": "MyConnection",
                    "Immutable": "not_a_boolean",
                    "Auto Increment": "maybe",
                }
            ],
            "Views": [
                {
                    "View": "MyView",
                    "Implements": "invalid[entity,list]syntax",
                    "In Model": "yes_but_not_boolean",
                }
            ],
        },
        {
            "In Properties sheet missing required column: 'Max Count'.",
            "In Properties sheet missing required column: 'Min Count'.",
            "In Properties sheet row 1 column 'Auto Increment' input should be a valid "
            "boolean, unable to interpret input.",
            "In Properties sheet row 1 column 'Immutable' input should be a valid boolean, unable to interpret input.",
            "In Views sheet row 1 column 'In Model' input should be a valid boolean, unable to interpret input.",
        },
        id="Invalid boolean and entity list values",
    )

    yield pytest.param(
        {
            "Metadata": [
                {
                    "Value": "my_space",  # Missing required "Key" field
                }
            ],
            "Properties": [
                {
                    "View": "MyView",
                    "Value Type": "text",  # Missing required "View Property" field
                    "Connection": "MyConnection",
                }
            ],
            "Views": [
                {
                    # Missing required "View" field entirely
                    "Name": "Some View Name",
                }
            ],
        },
        {
            "In Metadata sheet missing required column: 'Key'.",
            "In Properties sheet missing required column: 'Max Count'.",
            "In Properties sheet missing required column: 'Min Count'.",
            "In Properties sheet missing required column: 'View Property'.",
            "In Views sheet missing required column: 'View'.",
        },
        id="Missing required fields in various sheets",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data, expected_errors", list(invalid_test_cases()))
    def test_read_invalid_tables(
        self, data: dict[str, list[dict[str, CellValueType]]], expected_errors: set[str]
    ) -> None:
        importer = DMSTableImporter(data)
        with pytest.raises(DataModelImportError) as exc_info:
            importer._read_tables()
        actual_errors = {err.message for err in exc_info.value.errors}
        assert actual_errors == expected_errors


class TestTableSource:
    @pytest.mark.parametrize(
        "path,table_read,expected",
        [
            pytest.param((), {}, "", id="empty_path"),
            pytest.param(("MyTable",), {}, "table 'MyTable'", id="table_only"),
            pytest.param(("MyTable", 5), {}, "table 'MyTable' row 6", id="table_and_row"),
            pytest.param(("MyTable", 5, "field"), {}, "table 'MyTable' row 6 column 'field'", id="table_row_column"),
            pytest.param(
                ("MyTable", 5),
                {"MyTable": SpreadsheetReadContext(header_row=2, empty_rows=[3, 5], is_one_indexed=True)},
                "table 'MyTable' row 10",
                id="with_spreadsheet_read",
            ),
            pytest.param(("Views", 1, "externalId"), {}, "table 'Views' row 2 column 'View'", id="with_field_mapping"),
            pytest.param(
                ("MyTable", 1, "field", "nested", "path"),
                {},
                "table 'MyTable' row 2 column 'field' -> nested.path",
                id="with_extra_path_elements",
            ),
            pytest.param((123, 5, "field"), {}, "row 6 column 'field'", id="non_string_table_id"),
            pytest.param(
                ("MyTable", "not_int", "field"), {}, "table 'MyTable' column 'field'", id="non_int_row_number"
            ),
            pytest.param((0, 5), {}, "row 6", id="row_only"),
            pytest.param((0, "not_int", "field"), {}, "column 'field'", id="column_only"),
            pytest.param(
                ("MyTable", 1, "field", "extra"), {}, "table 'MyTable' row 2 column 'field'", id="path_length_exactly_4"
            ),
            pytest.param(
                ("MyTable", 1, "field", "a", "b", "c"),
                {},
                "table 'MyTable' row 2 column 'field' -> a.b.c",
                id="path_length_greater_than_4",
            ),
        ],
    )
    def test_location(
        self, path: tuple[int | str, ...], table_read: dict[str, SpreadsheetReadContext], expected: str
    ) -> None:
        source = TableSource("test_source", table_read)
        assert source.location(path) == expected

    @pytest.mark.parametrize(
        "table_id,row_no,table_read,expected",
        [
            pytest.param(
                "MyTable",
                5,
                {"MyTable": SpreadsheetReadContext(header_row=2, empty_rows=[1, 3])},
                10,  # 5 + 2 (header) + 2 (empty rows before 5) + 1 (1-indexed)
                id="with_table_read",
            ),
            pytest.param("MyTable", 5, {}, 6, id="without_table_read"),
            pytest.param(None, 5, {}, 6, id="none_table_id"),
            pytest.param("", 3, {"": SpreadsheetReadContext(header_row=5)}, 4, id="falsy_table_id"),
        ],
    )
    def test_adjust_row_number(
        self, table_id: str | None, row_no: int, table_read: dict[str, SpreadsheetReadContext], expected: int
    ) -> None:
        source = TableSource("test_source", table_read)
        assert source.adjust_row_number(table_id, row_no) == expected

    @pytest.mark.parametrize(
        "table_id,field,expected",
        [
            pytest.param("Views", "externalId", "View", id="views_table_external_id"),
            pytest.param("Views", "space", "View", id="views_table_space"),
            pytest.param("UnknownTable", "someField", "someField", id="unknown_table"),
            pytest.param(None, "someField", "someField", id="none_table_id"),
            pytest.param("Views", "unmappedField", "unmappedField", id="unmapped_field_in_mapped_table"),
        ],
    )
    def test_field_to_column(self, table_id: str | None, field: str, expected: str) -> None:
        assert TableSource.field_to_column(table_id, field) == expected

    @pytest.mark.parametrize(
        "table_id,expected_has_mapping,expected_external_id",
        [
            pytest.param("Views", True, "View", id="string_table_id_views"),
            pytest.param(123, False, None, id="non_string_table_id"),
            pytest.param(None, False, None, id="none_table_id"),
            pytest.param("UnknownTable", False, None, id="unknown_table"),
        ],
    )
    def test_field_mapping(
        self, table_id: str | int | None, expected_has_mapping: bool, expected_external_id: str | None
    ) -> None:
        mapping = TableSource.field_mapping(table_id)
        if expected_has_mapping:
            assert mapping is not None
            assert "externalId" in mapping
            assert mapping["externalId"] == expected_external_id
        else:
            assert mapping is None


class TestSpreadsheetRead:
    @pytest.mark.parametrize(
        "row,read,expected",
        [
            pytest.param(
                5,
                SpreadsheetReadContext(header_row=1, empty_rows=[], skipped_rows=[], is_one_indexed=True),
                7,  # 5 + 1 (header) + 1 (one_indexed)
                id="basic_case_with_one_indexing",
            ),
            pytest.param(
                5,
                SpreadsheetReadContext(header_row=2, empty_rows=[1, 3, 6], skipped_rows=[], is_one_indexed=True),
                11,  # 5->6 (empty 1)->7 (empty 3)->8 (empty 6) + 2 (header) + 1 (one_indexed)
                id="with_empty_rows",
            ),
            pytest.param(
                3,
                SpreadsheetReadContext(header_row=1, empty_rows=[2], skipped_rows=[1, 4], is_one_indexed=False),
                7,  # 3->4 (empty 2)->5 (skipped 1) + 1 (header) + 0 (zero_indexed)
                id="with_empty_and_skipped_rows_zero_indexed",
            ),
            pytest.param(
                2,
                SpreadsheetReadContext(header_row=3, empty_rows=[1, 5], skipped_rows=[2, 6], is_one_indexed=True),
                8,  # 2->3 (empty 1)->4 (skipped 2) + 3 (header) + 1 (one_indexed)
                id="complex_case_with_all_adjustments",
            ),
        ],
    )
    def test_adjusted_row_number(self, row: int, read: SpreadsheetReadContext, expected: int) -> None:
        assert read.adjusted_row_number(row) == expected
