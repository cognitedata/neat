from cognite.neat._rules.models import DMSInputRules
from cognite.neat._rules.models.dms import DMSInputContainer, DMSInputMetadata, DMSInputProperty, DMSInputView
from cognite.neat._rules.transformers import StandardizeNaming


class TestStandardizeNaming:
    def test_transform_dms(self) -> None:
        dms = DMSInputRules(
            metadata=DMSInputMetadata("my_spac", "MyModel", "me", "v1"),
            properties=[
                DMSInputProperty(
                    "my_poorly_formatted_view",
                    "and_sTranGeLY_named_property",
                    "text",
                    container="my_container",
                    container_property="my_property",
                )
            ],
            views=[DMSInputView("my_poorly_formatted_view")],
            containers=[DMSInputContainer("my_container")],
        )

        transformed = StandardizeNaming().transform(dms.as_verified_rules())

        assert transformed.views[0].view == "MyPoorlyFormattedView"
        assert transformed.properties[0].view_property == "andStrangelyNamedProperty"
        assert transformed.properties[0].container == "MyContainer"
