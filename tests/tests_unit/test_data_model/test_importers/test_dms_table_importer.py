from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.importers._table_importer.source import SpreadsheetRead, TableSource
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
                    "Name": "space",
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
                    "Value": "my_space",  # Missing required "Name" field
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
            "In Metadata sheet missing required column: 'Name'.",
            "In Properties sheet missing required column: 'Max Count'.",
            "In Properties sheet missing required column: 'Min Count'.",
            "In Properties sheet missing required column: 'View Property'.",
            "In Views sheet missing required column: 'View'.",
        },
        id="Missing required fields in various sheets",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data, expected_errors", list(invalid_test_cases()))
    def test_read_invalid_tables(self, data: dict[str, list[dict[str, CellValue]]], expected_errors: set[str]) -> None:
        importer = DMSTableImporter(data)
        with pytest.raises(ModelImportError) as exc_info:
            importer._read_tables()
        actual_errors = {err.message for err in exc_info.value.errors}
        assert actual_errors == expected_errors


class TestTableSource:
    def test_location_empty_path(self):
        source = TableSource("test_source")
        assert source.location(()) == ""

    def test_location_table_only(self):
        source = TableSource("test_source")
        assert source.location(("MyTable",)) == "table 'MyTable'"

    def test_location_table_and_row(self):
        source = TableSource("test_source")
        assert source.location(("MyTable", 5)) == "table 'MyTable' row 6"

    def test_location_table_row_column(self):
        source = TableSource("test_source")
        assert source.location(("MyTable", 5, "field")) == "table 'MyTable' row 6 column 'field'"

    def test_location_with_spreadsheet_read(self):
        source = TableSource(
            "test_source", {"MyTable": SpreadsheetRead(header_row=2, empty_rows=[3, 5], is_one_indexed=True)}
        )
        # Row 5 should be adjusted for header_row=2, empty_rows=[3,5], and 1-indexing
        assert source.location(("MyTable", 5)) == "table 'MyTable' row 10"

    def test_location_with_field_mapping(self):
        source = TableSource("test_source")
        # Test with a table that has field mapping (Views table)
        assert source.location(("Views", 1, "externalId")) == "table 'Views' row 2 column 'View'"

    def test_location_with_extra_path_elements(self):
        source = TableSource("test_source")
        assert (
            source.location(("MyTable", 1, "field", "nested", "path"))
            == "table 'MyTable' row 2 column 'field' -> nested.path"
        )

    def test_location_non_string_table_id(self):
        source = TableSource("test_source")
        assert source.location((123, 5, "field")) == "row 6 column 'field'"

    def test_location_non_int_row_number(self):
        source = TableSource("test_source")
        assert source.location(("MyTable", "not_int", "field")) == "table 'MyTable' column 'field'"

    def test_adjust_row_number_with_table_read(self):
        spreadsheet_read = SpreadsheetRead(header_row=2, empty_rows=[1, 3])
        source = TableSource("test_source", {"MyTable": spreadsheet_read})
        assert source.adjust_row_number("MyTable", 5) == 10

    def test_adjust_row_number_without_table_read(self):
        source = TableSource("test_source")
        assert source.adjust_row_number("MyTable", 5) == 6

    def test_adjust_row_number_none_table_id(self):
        source = TableSource("test_source")
        assert source.adjust_row_number(None, 5) == 6

    def test_field_to_column_with_mapping(self):
        # Test Views table which has field mapping
        assert TableSource.field_to_column("Views", "externalId") == "View"
        assert TableSource.field_to_column("Views", "space") == "View"

    def test_field_to_column_without_mapping(self):
        assert TableSource.field_to_column("UnknownTable", "someField") == "someField"
        assert TableSource.field_to_column(None, "someField") == "someField"

    def test_field_mapping_with_string_table_id(self):
        mapping = TableSource.field_mapping("Views")
        assert mapping is not None
        assert "externalId" in mapping
        assert mapping["externalId"] == "View"

    def test_field_mapping_with_non_string_table_id(self):
        assert TableSource.field_mapping(123) is None
        assert TableSource.field_mapping(None) is None

    def test_field_mapping_with_unknown_table(self):
        assert TableSource.field_mapping("UnknownTable") is None

    def test_location_row_only(self):
        source = TableSource("test_source")
        assert source.location((0, 5)) == "row 6"

    def test_location_column_only(self):
        source = TableSource("test_source")
        assert source.location((0, "not_int", "field")) == "column 'field'"

    def test_location_path_length_exactly_4(self):
        source = TableSource("test_source")
        assert source.location(("MyTable", 1, "field", "extra")) == "table 'MyTable' row 2 column 'field'"

    def test_location_path_length_greater_than_4(self):
        source = TableSource("test_source")
        assert (
            source.location(("MyTable", 1, "field", "a", "b", "c")) == "table 'MyTable' row 2 column 'field' -> a.b.c"
        )

    def test_field_to_column_unmapped_field_in_mapped_table(self):
        # Test field that doesn't exist in the mapping for a mapped table
        assert TableSource.field_to_column("Views", "unmappedField") == "unmappedField"

    def test_adjust_row_number_with_falsy_table_id(self):
        source = TableSource("test_source", {"": SpreadsheetRead(header_row=5)})
        # Empty string is falsy, so should use default behavior
        assert source.adjust_row_number("", 3) == 4
