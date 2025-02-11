from cognite.client import data_modeling as dm

from cognite.neat._client._api.schema import SchemaAPI
from cognite.neat._client.data_classes.schema import DMSSchema


class TestSchemaAPI:
    def test_get_hierarchical_properties(self, cognite_core_schema: DMSSchema) -> None:
        schema = cognite_core_schema
        hierarchical_properties = SchemaAPI.get_hierarchical_properties(schema.views.values())
        assert hierarchical_properties == {dm.ViewId("cdf_cdm", "CogniteAsset", "v1"): {"parent"}}
