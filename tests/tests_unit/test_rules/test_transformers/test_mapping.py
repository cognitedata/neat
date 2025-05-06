from cognite.neat.core._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat.core._rules.models.entities import ContainerEntity, ViewEntity
from cognite.neat.core._rules.transformers import RuleMapper


class TestClassicToCoreMapper:
    def test_map_single_property(self) -> None:
        classic = "classic"
        input_ = DMSInputRules(
            metadata=DMSInputMetadata(
                space=classic,
                external_id=classic,
                version="1.0",
                creator="neat",
                name="TheClassic",
            ),
            properties=[
                DMSInputProperty(
                    view="MyAsset",
                    view_property="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                )
            ],
            views=[DMSInputView(view="MyAsset")],
            containers=[DMSInputContainer(container="Asset")],
        ).as_verified_rules()

        input_rules = input_

        mapping = DMSInputRules(
            metadata=DMSInputMetadata(
                space="mapping",
                external_id="mapping",
                version="1.0",
                creator="me",
            ),
            properties=[
                DMSInputProperty(
                    view="MyAsset",
                    view_property="name",
                    value_type="text",
                    container="cdf_cdm:CogniteAsset",
                    container_property="name",
                )
            ],
            views=[
                DMSInputView(view="MyAsset", implements="cdf_cdm:CogniteAsset(version=v1)"),
            ],
        ).as_verified_rules()

        transformed = RuleMapper(mapping).transform(input_rules)

        assert len(transformed.properties) == 1
        prop = transformed.properties[0]
        assert prop.container == ContainerEntity.load("cdf_cdm:CogniteAsset")
        assert prop.container_property == "name"

        assert len(transformed.views) == 1
        first = transformed.views[0]
        assert first.implements == [ViewEntity.load("cdf_cdm:CogniteAsset(version=v1)")]
        assert first.view == ViewEntity.load(f"{classic}:MyAsset(version=1.0)")
