from collections import defaultdict
from collections.abc import Sequence

import pytest
from cognite.client.data_classes.data_modeling import ViewId, ViewIdentifier, ViewList

from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.models import (
    ConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import (
    ConceptEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.physical import (
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.v0.core._data_model.models.physical._verified import PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import (
    AddCogniteProperties,
    StandardizeNaming,
    SubsetConceptualDataModel,
    SubsetPhysicalDataModel,
    ToDMSCompliantEntities,
)
from cognite.neat.v0.core._issues.errors._general import NeatValueError


class TestStandardizeNaming:
    def test_transform_dms(self) -> None:
        dms = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata("my_spac", "MyModel", "me", "v1"),
            properties=[
                UnverifiedPhysicalProperty(
                    "my_poorly_formatted_view",
                    "and_strangely_named_property",
                    "text",
                    container="my_container",
                    container_property="my_property",
                )
            ],
            views=[UnverifiedPhysicalView("my_poorly_formatted_view")],
            containers=[UnverifiedPhysicalContainer("my_container")],
        )

        transformed = StandardizeNaming().transform(dms.as_verified_data_model())

        assert transformed.views[0].view.suffix == "MyPoorlyFormattedView"
        assert transformed.properties[0].view_property == "andStrangelyNamedProperty"
        assert transformed.properties[0].view.suffix == "MyPoorlyFormattedView"
        assert transformed.properties[0].container.suffix == "MyContainer"
        assert transformed.containers[0].container.suffix == "MyContainer"

    def test_transform_information(self) -> None:
        class_name = "not_a_good_cLass_NAME"
        information = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "MyModel", "me", "v1"),
            properties=[
                UnverifiedConceptualProperty(class_name, "TAG_NAME", "string", max_count=1),
            ],
            concepts=[UnverifiedConcept(class_name)],
        )

        res: ConceptualDataModel = StandardizeNaming().transform(information.as_verified_data_model())

        assert res.properties[0].property_ == "tagName"
        assert res.properties[0].concept.suffix == "NotAGoodCLassNAME"
        assert res.concepts[0].concept.suffix == "NotAGoodCLassNAME"


class TestToInformationCompliantEntities:
    def test_transform_information(self) -> None:
        class_name = "not_a_good_cLass_NAME"
        information = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "MyModel", "me", "v1"),
            properties=[
                UnverifiedConceptualProperty(class_name, "TAG_NAME", "string", max_count=1),
                UnverifiedConceptualProperty(class_name, "State(Previous)", "string", max_count=1),
                UnverifiedConceptualProperty(class_name, "P&ID", "string", max_count=1),
            ],
            concepts=[UnverifiedConcept(class_name)],
        )

        res: ConceptualDataModel = (
            ToDMSCompliantEntities(rename_warning="raise")
            .transform(ImportedDataModel(information, {}))
            .unverified_data_model.as_verified_data_model()
        )

        assert res.properties[0].property_ == "TAG_NAME"
        assert res.properties[0].concept.suffix == "not_a_good_cLass_NAME"
        assert res.concepts[0].concept.suffix == "not_a_good_cLass_NAME"

        assert res.properties[1].property_ == "statePrevious"
        assert res.properties[2].property_ == "pId"


class TestDataModelSubsetting:
    def test_subset_information_rules(self, david_rules: ConceptualDataModel) -> None:
        concept = ConceptEntity.load("power:GeoLocation")
        subset = SubsetConceptualDataModel({concept}).transform(david_rules)

        assert subset.concepts[0].concept == concept
        assert len(subset.concepts) == 1

    def test_subset_information_rules_fails(self, david_rules: PhysicalDataModel) -> None:
        class_ = ConceptEntity.load("power:GeoLooocation")

        with pytest.raises(NeatValueError):
            _ = SubsetConceptualDataModel({class_}).transform(david_rules)

    def test_subset_dms_rules(self, alice_rules: PhysicalDataModel) -> None:
        view = ViewEntity.load("power:GeoLocation(version=0.1.0)")
        subset = SubsetPhysicalDataModel({view}).transform(alice_rules)

        assert subset.views[0].view == view
        assert len(subset.views) == 1

    def test_subset_dms_rules_fails(self, alice_rules: PhysicalDataModel) -> None:
        view = ViewEntity.load("power:GeoLooocation(version=0.1.0)")

        with pytest.raises(NeatValueError):
            _ = SubsetPhysicalDataModel({view}).transform(alice_rules)


class TestAddCogniteProperties:
    def test_add_cognite_properties(self, cognite_core_schema: DMSSchema) -> None:
        unverified_conceptual_dm = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "MyModel", "v1", "doctrino"),
            properties=[],
            concepts=[
                UnverifiedConcept("PowerGeneratingUnit", implements="cdf_cdm:CogniteAsset(version=v1)"),
                UnverifiedConcept("WindTurbine", implements="PowerGeneratingUnit"),
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

            result = AddCogniteProperties(client).transform(ImportedDataModel(unverified_conceptual_dm, {}))
        assert result.unverified_data_model is not None
        actual_concepts = {str(c.concept) for c in result.unverified_data_model.concepts}
        expected_concepts = (
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
        assert actual_concepts == expected_concepts
        cognite_asset = cognite_core_schema.views[ViewId("cdf_cdm", "CogniteAsset", "v1")]
        expected_properties = set(cognite_asset.properties.keys())
        expected_properties |= {
            prop_id
            for parent in cognite_asset.implements
            for prop_id in cognite_core_schema.views[parent].properties.keys()
        }

        properties_by_concept = defaultdict(set)
        for prop in result.unverified_data_model.properties:
            properties_by_concept[prop.concept.dump(prefix="my_space")].add(prop.property_)

        assert set(properties_by_concept.keys()) == {"PowerGeneratingUnit", "WindTurbine"}
        assert properties_by_concept["PowerGeneratingUnit"] == expected_properties
        assert properties_by_concept["WindTurbine"] == expected_properties
