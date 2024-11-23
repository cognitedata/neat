from cognite.neat._rules._shared import JustRules
from cognite.neat._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat._rules.models.entities import ContainerEntity, ViewEntity
from cognite.neat._rules.transformers import RuleMapper


class TestClassicToCoreMapper:
    def test_map_single_property(self) -> None:
        classic = "classic"
        core = "core"
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
            views=[
                DMSInputView(
                    view="MyAsset",
                )
            ],
            containers=[
                DMSInputContainer(
                    container="Asset",
                )
            ],
        ).as_rules()

        input_rules = JustRules(input_)

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
                DMSInputView(
                    view="MyAsset",
                    implements="cdf_cdm:CogniteAsset(version=v1)",
                )
            ],
        ).as_rules()

        transformed = RuleMapper(mapping).transform(input_rules).rules

        assert len(transformed.properties) == 1
        prop = transformed.properties[0]
        assert prop.container == ContainerEntity.load(f"{core}:CogniteAsset")
        assert prop.container_property == "name"

        assert len(transformed.views) == 2
        first = transformed.views[0]
        cognite_asset = ViewEntity.load(f"{core}:CogniteAsset(version=v1)")
        assert first.implements == [cognite_asset]
        second = transformed.views[1]
        assert second.view == cognite_asset
