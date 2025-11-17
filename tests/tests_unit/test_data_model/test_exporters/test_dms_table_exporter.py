from typing import Any

from cognite.neat._data_model.exporters import DMSTableExporter
from cognite.neat._data_model.models.dms import RequestSchema


class TestDMSTableExporter:
    def test_export_table_skip_properties_other_spaces(self, example_dms_schema_response: dict[str, Any]) -> None:
        """Test exporting DMS to table format while skipping properties in other spaces."""
        schema = RequestSchema.model_validate(example_dms_schema_response)
        assert len(schema.views) > 0, "Example DMS schema should have at least one view for this test."
        original_property_count = sum(len(view.properties) for view in schema.views)
        first = schema.views[0]
        view_other_space = first.model_copy(update={"space": "other_space"}, deep=True)
        schema.views.append(view_other_space)
        assert schema.data_model.views is not None, "Data model views should not be None."
        schema.data_model.views.append(view_other_space.as_reference())

        exporter = DMSTableExporter(skip_properties_in_other_spaces=True)

        tables = exporter.export(schema)

        assert len(tables["Properties"]) == original_property_count, "Properties from other spaces should be skipped."

        exporter = DMSTableExporter(skip_properties_in_other_spaces=False)
        tables = exporter.export(schema)
        assert len(tables["Properties"]) == original_property_count + len(view_other_space.properties), (
            "All properties should be included when not skipping other spaces."
        )
