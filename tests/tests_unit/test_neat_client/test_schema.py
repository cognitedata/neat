from cognite.client import data_modeling as dm

from cognite.neat._client._api.schema import SchemaAPI
from cognite.neat._client.data_classes.schema import DMSSchema


class TestSchemaAPI:
    def test_order_views_by_container_dependencies(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        external_ids = ["CogniteAsset", "CogniteDescribable", "CogniteSourceable", "CogniteVisualizable"]
        selected_views = {v_id: v for v_id, v in schema.views.items() if v_id.external_id in external_ids}
        selected_containers = [c for c in schema.containers.values() if c.external_id in external_ids]

        id_order, depend_on_self = SchemaAPI.order_views_by_container_dependencies(selected_views, selected_containers)
        # The three first ones are not dependent on any other view
        assert id_order[-1].external_id == "CogniteAsset"
        assert depend_on_self == {dm.ViewId("cdf_cdm", "CogniteAsset", "v1"): {"parent", "path", "root"}}
