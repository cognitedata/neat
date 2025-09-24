from cognite.neat.v0.core._data_model.models.entities import ContainerEntity, ViewEntity
from cognite.neat.v0.core._data_model.models.physical import (
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalDataModel,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.v0.core._data_model.transformers import PhysicalDataModelMapper


class TestClassicToCoreMapper:
    def test_map_single_property(self) -> None:
        classic = "classic"
        input_ = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata(
                space=classic,
                external_id=classic,
                version="1.0",
                creator="neat",
                name="TheClassic",
            ),
            properties=[
                UnverifiedPhysicalProperty(
                    view="MyAsset",
                    view_property="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                )
            ],
            views=[UnverifiedPhysicalView(view="MyAsset")],
            containers=[UnverifiedPhysicalContainer(container="Asset")],
        ).as_verified_data_model()

        input_rules = input_

        mapping = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata(
                space="mapping",
                external_id="mapping",
                version="1.0",
                creator="me",
            ),
            properties=[
                UnverifiedPhysicalProperty(
                    view="MyAsset",
                    view_property="name",
                    value_type="text",
                    container="cdf_cdm:CogniteAsset",
                    container_property="name",
                )
            ],
            views=[
                UnverifiedPhysicalView(view="MyAsset", implements="cdf_cdm:CogniteAsset(version=v1)"),
            ],
        ).as_verified_data_model()

        transformed = PhysicalDataModelMapper(mapping).transform(input_rules)

        assert len(transformed.properties) == 1
        prop = transformed.properties[0]
        assert prop.container == ContainerEntity.load("cdf_cdm:CogniteAsset")
        assert prop.container_property == "name"

        assert len(transformed.views) == 1
        first = transformed.views[0]
        assert first.implements == [ViewEntity.load("cdf_cdm:CogniteAsset(version=v1)")]
        assert first.view == ViewEntity.load(f"{classic}:MyAsset(version=1.0)")
