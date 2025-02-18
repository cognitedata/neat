from cognite.client import data_modeling as dm

from cognite.neat._client._api.schema import SchemaAPI
from cognite.neat._client.data_classes.schema import DMSSchema


class TestSchemaAPI:
    def test_get_hierarchical_properties(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        hierarchical_properties = SchemaAPI.get_hierarchical_properties(schema.views.values())
        assert hierarchical_properties == {dm.ViewId("cdf_cdm", "CogniteAsset", "v1"): {"parent"}}

    def test_get_view_order_by_direct_relation_constraints(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        selected_views = {"CogniteAsset", "CogniteFile", "CogniteEquipment", "CogniteTimeSeries", "CogniteActivity"}
        view_order = SchemaAPI.get_view_order_by_direct_relation_constraints(
            [view for view in schema.views.values() if view.external_id in selected_views]
        )
        external_ids = [view.external_id for view in view_order]
        assert external_ids == [
            "CogniteAsset",
            "CogniteFile",
            "CogniteEquipment",
            "CogniteTimeSeries",
            "CogniteActivity",
        ]
