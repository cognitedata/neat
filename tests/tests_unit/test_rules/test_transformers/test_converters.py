from collections import defaultdict
from collections.abc import Sequence

import pytest
from cognite.client.data_classes.data_modeling import ViewId, ViewIdentifier, ViewList

from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.models import DMSInputRules, InformationRules
from cognite.neat.core._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputView,
)
from cognite.neat.core._rules.models.dms._rules import DMSRules
from cognite.neat.core._rules.models.entities._single_value import (
    ClassEntity,
    ViewEntity,
)
from cognite.neat.core._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
)
from cognite.neat.core._rules.transformers import (
    AddCogniteProperties,
    StandardizeNaming,
    SubsetDMSRules,
    SubsetInformationRules,
    ToDMSCompliantEntities,
)


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


class TestRulesSubsetting:
    def test_subset_information_rules(self, david_rules: InformationRules) -> None:
        class_ = ClassEntity.load("power:GeoLocation")
        subset = SubsetInformationRules({class_}).transform(david_rules)

        assert subset.classes[0].class_ == class_
        assert len(subset.classes) == 1

    def test_subset_information_rules_fails(self, david_rules: DMSRules) -> None:
        class_ = ClassEntity.load("power:GeoLooocation")

        with pytest.raises(NeatValueError):
            _ = SubsetInformationRules({class_}).transform(david_rules)

    def test_subset_dms_rules(self, alice_rules: DMSRules) -> None:
        view = ViewEntity.load("power:GeoLocation(version=0.1.0)")
        subset = SubsetDMSRules({view}).transform(alice_rules)

        assert subset.views[0].view == view
        assert len(subset.views) == 1

    def test_subset_dms_rules_fails(self, alice_rules: DMSRules) -> None:
        view = ViewEntity.load("power:GeoLooocation(version=0.1.0)")

        with pytest.raises(NeatValueError):
            _ = SubsetDMSRules({view}).transform(alice_rules)


class TestAddCogniteProperties:
    def test_add_cognite_properties(self, cognite_core_schema: DMSSchema) -> None:
        input_rules = InformationInputRules(
            metadata=InformationInputMetadata("my_space", "MyModel", "v1", "doctrino"),
            properties=[],
            classes=[
                InformationInputClass("PowerGeneratingUnit", implements="cdf_cdm:CogniteAsset(version=v1)"),
                InformationInputClass("WindTurbine", implements="PowerGeneratingUnit"),
            ],
        )
        read_model = cognite_core_schema.as_read_model()
        views_by_id = {view.as_id(): view for view in read_model.views}

        def cognite_core(ids: ViewIdentifier | Sequence[ViewIdentifier], **kwargs) -> ViewList:
            ids = [ids] if isinstance(ids, ViewId | tuple) else ids
            view_ids = [ViewId.load(id_) for id_ in ids]

            return ViewList([views_by_id[id_] for id_ in view_ids])

        with monkeypatch_neat_client() as client:
            client.data_modeling.views.retrieve.side_effect = cognite_core

            result = AddCogniteProperties(client).transform(ReadRules(input_rules, {}))
        assert result.rules is not None
        actual_classes = {str(c.class_) for c in result.rules.classes}
        expected_classes = (
            {"PowerGeneratingUnit", "WindTurbine"}
            | {
                f"{view_id.space}:{view_id.external_id}(version={view_id.version})"
                for view_id in cognite_core_schema.views.keys()
            }
            # These classes are not reachable from the CogniteAsset
        ) - {
            "cdf_cdm:CogniteDiagramAnnotation(version=v1)",
            "cdf_cdm:CognitePointCloudModel(version=v1)",
            "cdf_cdm:CognitePointCloudRevision(version=v1)",
        }
        assert actual_classes == expected_classes
        cognite_asset = cognite_core_schema.views[ViewId("cdf_cdm", "CogniteAsset", "v1")]
        expected_properties = set(cognite_asset.properties.keys())
        expected_properties |= {
            prop_id
            for parent in cognite_asset.implements
            for prop_id in cognite_core_schema.views[parent].properties.keys()
        }

        properties_by_class = defaultdict(set)
        for prop in result.rules.properties:
            properties_by_class[prop.class_.dump(prefix="my_space")].add(prop.property_)

        assert set(properties_by_class.keys()) == {"PowerGeneratingUnit", "WindTurbine"}
        assert properties_by_class["PowerGeneratingUnit"] == expected_properties
        assert properties_by_class["WindTurbine"] == expected_properties
