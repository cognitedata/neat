from typing import Any

from cognite.neat._data_model._constants import DEFAULT_MAX_LIST_SIZE, DEFAULT_MAX_LIST_SIZE_DIRECT_RELATIONS
from cognite.neat._data_model.exporters import DMSTableExporter
from cognite.neat._data_model.models.dms import DirectNodeRelation, ListablePropertyTypeDefinition, RequestSchema


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

    def test_export_table_write_default_max_list_size(self, example_dms_schema_response: dict[str, Any]) -> None:
        """Test exporting DMS to table format with default max list size."""
        schema = RequestSchema.model_validate(example_dms_schema_response)
        assert len(schema.containers) > 0, "Example DMS schema should have at least one container for this test."
        container = schema.containers[0]
        assert len(container.properties) > 0, "Container should have properties for this test."
        prop_id, prop = next(
            (
                (prop_id, prop)
                for prop_id, prop in container.properties.items()
                if isinstance(prop.type, ListablePropertyTypeDefinition)
            ),
            (None, None),
        )
        assert prop is not None, "Container should have at least one listable property."
        type_ = prop.type
        assert isinstance(type_, ListablePropertyTypeDefinition)
        type_.max_list_size = None  # Remove max_list_size to test default behavior
        type_.list = True

        exporter = DMSTableExporter()
        tables = exporter.export(schema)

        assert "Properties" in tables, "Properties sheet should be present in the exported tables."
        assert len(tables["Properties"]) > 0, "Properties sheet should contain entries."
        exported_prop = next(
            (
                row
                for row in tables["Properties"]
                if row["Container Property"] == prop_id and row["Container"] == container.external_id
            ),
            None,
        )
        assert exported_prop is not None, "Exported property should be found in the Properties sheet."
        max_list_size = (
            DEFAULT_MAX_LIST_SIZE_DIRECT_RELATIONS
            if isinstance(prop.type, DirectNodeRelation)
            else DEFAULT_MAX_LIST_SIZE
        )
        assert exported_prop["Max Count"] == max_list_size
