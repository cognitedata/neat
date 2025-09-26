from cognite.client import data_modeling as dm

from cognite.neat.v0.core._client._api.schema import SchemaAPI
from cognite.neat.v0.core._client.data_classes.schema import DMSSchema


class TestSchemaAPI:
    def test_get_hierarchical_properties(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        hierarchical_properties = SchemaAPI.get_hierarchical_properties(schema.views.values())
        assert hierarchical_properties == {dm.ViewId("cdf_cdm", "CogniteAsset", "v1"): {"parent"}}

    def test_get_view_order_by_direct_relation_constraints(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        read_views = schema.as_read_model().views
        view_order = SchemaAPI.get_view_order_by_direct_relation_constraints(read_views)
        selected_external_ids = [
            "CogniteSourceSystem",
            "CogniteAsset",
            "CogniteFile",
            "CogniteEquipment",
            "CogniteTimeSeries",
            "CogniteActivity",
        ]
        external_ids = [view.external_id for view in view_order if view.external_id in set(selected_external_ids)]
        # The topological order is not unique, so we cannot compare the full order.
        # All other views depend on the source system so that must be first.
        assert external_ids[0] == "CogniteSourceSystem"
