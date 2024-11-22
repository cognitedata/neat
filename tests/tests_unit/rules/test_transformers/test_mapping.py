from cognite.neat._rules._shared import JustRules
from cognite.neat._rules.models._base_rules import ContainerDestinationProperty, ContainerProperty, ViewRef
from cognite.neat._rules.models.data_types import String
from cognite.neat._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat._rules.models.entities import ContainerEntity, ViewEntity
from cognite.neat._rules.models.mapping import Mapping, MappingList, RuleMapping
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

        mapping = RuleMapping(
            properties=MappingList[ContainerProperty, ContainerDestinationProperty](
                [
                    Mapping(
                        source=ContainerProperty(
                            container=ContainerEntity.load(f"{classic}:MyAsset"),
                            property_="name",
                        ),
                        destination=ContainerDestinationProperty(
                            container=ContainerEntity.load(f"{core}:CogniteAsset"),
                            property_="name",
                            value_type=String(),
                        ),
                    )
                ]
            ),
            views=MappingList[ViewRef, ViewRef](
                [
                    Mapping(
                        source=ViewRef(view=ViewEntity.load(f"{classic}:MyAsset(version=1.0)")),
                        destination=ViewRef(view=ViewEntity.load(f"{core}:CogniteAsset(version=v1)")),
                    )
                ]
            ),
        )

        transformed = RuleMapper(mapping).transform(input_rules).rules

        assert len(transformed.properties) == 1
        prop = transformed.properties[0]
        assert prop.container == ContainerEntity.load(f"{core}:CogniteAsset")
        assert prop.property_ == "name"

        assert len(transformed.views) == 1
        view = transformed.views[0]
        assert view.implements == ViewEntity.load(f"{core}:CogniteAsset(version=v1)")
