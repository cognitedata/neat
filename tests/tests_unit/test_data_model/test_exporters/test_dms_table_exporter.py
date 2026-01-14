from typing import Any

import pytest

from cognite.neat._data_model._constants import DEFAULT_MAX_LIST_SIZE, DEFAULT_MAX_LIST_SIZE_DIRECT_RELATIONS
from cognite.neat._data_model.exporters import DMSTableExporter
from cognite.neat._data_model.exporters._table_exporter.writer import DMSTableWriter
from cognite.neat._data_model.importers._table_importer.data_classes import (
    EntityTableFilter,
    RAWFilterTableFilter,
    TableViewFilter,
)
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    DirectNodeRelation,
    EqualsFilterData,
    Filter,
    HasDataFilter,
    InFilterData,
    ListablePropertyTypeDefinition,
    RequestSchema,
    ViewReference,
)
from cognite.neat._data_model.models.entities import ParsedEntity


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


class TestDMSTableWriter:
    DEFAULT_SPACE = "default_space"
    DEFAULT_VERSION = "default_version"

    @pytest.mark.parametrize(
        "filter, expected",
        [
            pytest.param(
                {"hasData": HasDataFilter(data=[ContainerReference(space="my_space", external_id="container1")])},
                EntityTableFilter(type="hasData", entities=[ParsedEntity("my_space", "container1", {})]),
                id="HasData filter with one container",
            ),
            pytest.param(
                {
                    "equals": EqualsFilterData(
                        property=["node", "type"], value={"space": "my_space", "externalId": "node1"}
                    )
                },
                EntityTableFilter(type="nodeType", entities=[ParsedEntity("my_space", "node1", {})]),
                id="Equals filter",
            ),
            pytest.param(
                {
                    "in": InFilterData(
                        property=["node", "type"],
                        values=[
                            {"space": "my_space", "externalId": "node1"},
                            {"space": "my_space", "externalId": "node2"},
                        ],
                    )
                },
                EntityTableFilter(
                    type="nodeType",
                    entities=[
                        ParsedEntity("my_space", "node1", {}),
                        ParsedEntity("my_space", "node2", {}),
                    ],
                ),
                id="In filter with multiple nodes",
            ),
            pytest.param(
                {"hasData": HasDataFilter(data=[ContainerReference(space=DEFAULT_SPACE, external_id="container37")])},
                EntityTableFilter(
                    type="hasData",
                    entities=[ParsedEntity("", "container37", {})],
                ),
                id="HasData filter with default space",
            ),
            pytest.param(None, "", id="No filter"),
            pytest.param(
                {
                    "hasData": HasDataFilter(
                        data=[
                            ContainerReference(space=DEFAULT_SPACE, external_id="container1"),
                            ViewReference(space="other_space", external_id="view1", version="v1"),
                        ]
                    )
                },
                RAWFilterTableFilter(
                    filter='{"hasData":[{"space":"default_space","external_id":"container1","type":"container"},{"space":"other_space","external_id":"view1","version":"v1","type":"view"}]'
                ),
                id="Raw filter",
            ),
        ],
    )
    def test_write_view_filter(self, filter: Filter | None, expected: TableViewFilter) -> None:
        writer = DMSTableWriter(self.DEFAULT_SPACE, self.DEFAULT_VERSION, skip_properties_in_other_spaces=True)
        assert writer.write_view_filter(filter) == expected
