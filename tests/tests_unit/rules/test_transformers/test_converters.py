from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models import DMSInputRules, InformationRules
from cognite.neat._rules.models.dms import DMSInputContainer, DMSInputMetadata, DMSInputProperty, DMSInputView
from cognite.neat._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
)
from cognite.neat._rules.transformers import StandardizeNaming, ToDMSCompliantEntities


class TestStandardizeNaming:
    def test_transform_dms(self) -> None:
        dms = DMSInputRules(
            metadata=DMSInputMetadata("my_spac", "MyModel", "me", "v1"),
            properties=[
                DMSInputProperty(
                    "my_poorly_formatted_view",
                    "and_strangely_named_property",
                    "text",
                    container="my_container",
                    container_property="my_property",
                )
            ],
            views=[DMSInputView("my_poorly_formatted_view")],
            containers=[DMSInputContainer("my_container")],
        )

        transformed = StandardizeNaming().transform(dms.as_verified_rules())

        assert transformed.views[0].view.suffix == "MyPoorlyFormattedView"
        assert transformed.properties[0].view_property == "andStrangelyNamedProperty"
        assert transformed.properties[0].view.suffix == "MyPoorlyFormattedView"
        assert transformed.properties[0].container.suffix == "MyContainer"
        assert transformed.containers[0].container.suffix == "MyContainer"

    def test_transform_information(self) -> None:
        class_name = "not_a_good_cLass_NAME"
        information = InformationInputRules(
            metadata=InformationInputMetadata("my_space", "MyModel", "me", "v1"),
            properties=[
                InformationInputProperty(class_name, "TAG_NAME", "string", max_count=1),
            ],
            classes=[InformationInputClass(class_name)],
        )

        res: InformationRules = StandardizeNaming().transform(information.as_verified_rules())

        assert res.properties[0].property_ == "tagName"
        assert res.properties[0].class_.suffix == "NotAGoodCLassNAME"
        assert res.classes[0].class_.suffix == "NotAGoodCLassNAME"


class TestToInformationCompliantEntities:
    def test_transform_information(self) -> None:
        class_name = "not_a_good_cLass_NAME"
        information = InformationInputRules(
            metadata=InformationInputMetadata("my_space", "MyModel", "me", "v1"),
            properties=[
                InformationInputProperty(class_name, "TAG_NAME", "string", max_count=1),
                InformationInputProperty(class_name, "State(Previous)", "string", max_count=1),
                InformationInputProperty(class_name, "P&ID", "string", max_count=1),
            ],
            classes=[InformationInputClass(class_name)],
        )

        res: InformationRules = (
            ToDMSCompliantEntities(rename_warning="raise")
            .transform(ReadRules(information, {}))
            .rules.as_verified_rules()
        )

        assert res.properties[0].property_ == "TAG_NAME"
        assert res.properties[0].class_.suffix == "not_a_good_cLass_NAME"
        assert res.classes[0].class_.suffix == "not_a_good_cLass_NAME"

        assert res.properties[1].property_ == "statePrevious"
        assert res.properties[2].property_ == "pId"
