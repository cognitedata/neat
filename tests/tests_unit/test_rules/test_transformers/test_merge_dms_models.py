from cognite.neat.core._data_model.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat.core._data_model.transformers import MergeDMSRules


class TestMergeDMSRules:
    def test_merge_models(self) -> None:
        existing = DMSInputRules(
            metadata=DMSInputMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                DMSInputProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                DMSInputProperty(
                    "Equipment",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                DMSInputProperty(
                    "Equipment",
                    "asset",
                    "Asset",
                    connection="direct",
                    min_count=0,
                    max_count=1,
                    container="Equipment",
                    container_property="asset",
                ),
            ],
            views=[DMSInputView("Asset"), DMSInputView("Equipment")],
            containers=[
                DMSInputContainer("CogniteDescribable"),
                DMSInputContainer("CogniteEquipment"),
            ],
        ).as_verified_rules()
        additional = DMSInputRules(
            metadata=DMSInputMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                DMSInputProperty(
                    "MyAsset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="MyAssetContainer",
                    container_property="name",
                ),
                DMSInputProperty(
                    "MyAsset",
                    "tags",
                    "text",
                    min_count=0,
                    max_count=1000,
                    container="MyAssetContainer",
                    container_property="tags",
                ),
                DMSInputProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="description",
                ),
            ],
            views=[DMSInputView("MyAsset"), DMSInputView("Asset")],
            containers=[
                DMSInputContainer("MyAssetContainer"),
                DMSInputContainer("CogniteDescribable"),
            ],
        ).as_verified_rules()

        actual = MergeDMSRules(additional).transform(existing)

        assert len(actual.containers) == 3
        assert {c.container.suffix for c in actual.containers} == {
            "CogniteDescribable",
            "CogniteEquipment",
            "MyAssetContainer",
        }
        assert len(actual.views) == 3
        assert {v.view.suffix for v in actual.views} == {"MyAsset", "Asset", "Equipment"}
        assert len(actual.properties) == 5
        assert {(p.view.suffix, p.view_property) for p in actual.properties} == {
            ("MyAsset", "name"),
            ("MyAsset", "tags"),
            ("Asset", "name"),
            ("Equipment", "name"),
            ("Equipment", "asset"),
        }
