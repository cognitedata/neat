from collections.abc import Iterable

import pytest

from cognite.neat.core._data_model._shared import ImportedDataModel, UnverifiedDataModel
from cognite.neat.core._data_model.importers import DMSMergeImporter
from cognite.neat.core._data_model.importers._base import BaseImporter
from cognite.neat.core._data_model.models import (
    PhysicalDataModel,
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.core._data_model.models.physical import (
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.core._issues.errors import NeatError


class ImportAdditional(BaseImporter):
    def to_data_model(self) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        return ImportedDataModel(
            unverified_data_model=UnverifiedConceptualDataModel(
                metadata=UnverifiedConceptualMetadata(
                    external_id="my_model", version="1.0.0", space="neat", creator="doctrino"
                ),
                properties=[
                    UnverifiedConceptualProperty(
                        "MyAsset",
                        "location",
                        "text",
                        min_count=0,
                        max_count=1,
                    )
                ],
                concepts=[
                    UnverifiedConcept(
                        "MyAsset",
                        implements="CogniteAsset",
                    )
                ],
            ),
            context={},
        )


class ImportExisting(BaseImporter):
    def to_data_model(self) -> ImportedDataModel[UnverifiedPhysicalDataModel]:
        return ImportedDataModel(
            unverified_data_model=UnverifiedPhysicalDataModel(
                metadata=UnverifiedPhysicalMetadata(
                    external_id="my_model", version="1.0.0", space="neat", creator="doctrino"
                ),
                properties=[
                    UnverifiedPhysicalProperty(
                        "CogniteAsset",
                        "name",
                        "text",
                        min_count=0,
                        max_count=1,
                        container="CogniteDescribable",
                        container_property="name",
                    ),
                    UnverifiedPhysicalProperty(
                        "CogniteEquipment",
                        "name",
                        "text",
                        min_count=0,
                        max_count=1,
                        container="CogniteDescribable",
                        container_property="name",
                    ),
                    UnverifiedPhysicalProperty(
                        "CogniteEquipment",
                        "asset",
                        "CogniteAsset",
                        connection="direct",
                        min_count=0,
                        max_count=10,
                        container="CogniteEquipment",
                        container_property="asset",
                    ),
                ],
                views=[UnverifiedPhysicalView("CogniteAsset"), UnverifiedPhysicalView("CogniteEquipment")],
                containers=[
                    UnverifiedPhysicalContainer("CogniteDescribable"),
                    UnverifiedPhysicalContainer("CogniteEquipment"),
                ],
            ),
            context={},
        )


def merge_importer_unhappy_test_cases() -> Iterable:
    """Test cases for unhappy path of merge importer."""
    yield pytest.param(
        ImportedDataModel(None, {}),
        ImportedDataModel(None, {}),
        "NeatValueError: Cannot merge. Existing data model failed read.",
        id="Missing existing rules",
    )
    yield pytest.param(
        ImportedDataModel(
            UnverifiedPhysicalDataModel(
                UnverifiedPhysicalMetadata(
                    external_id="my_model", version="1.0.0", creator="doctrino", space="my_space"
                ),
                [],
                [],
            ),
            {},
        ),
        ImportedDataModel(None, {}),
        "NeatValueError: Cannot merge. Additional data model failed read.",
        id="Missing additional rules",
    )


class TestMergeImporter:
    def test_merge_importer_happy_path(self) -> None:
        importer = DMSMergeImporter(
            existing=ImportExisting(),
            additional=ImportAdditional(),
        )
        input_rules = importer.to_data_model()
        assert input_rules.unverified_data_model is not None
        model = input_rules.unverified_data_model.as_verified_data_model()
        assert isinstance(model, PhysicalDataModel)
        assert {view.view.external_id for view in model.views} == {"CogniteAsset", "CogniteEquipment", "MyAsset"}

        assert {(prop.view.external_id, prop.view_property) for prop in model.properties} == {
            ("CogniteAsset", "name"),
            ("CogniteEquipment", "name"),
            ("CogniteEquipment", "asset"),
            ("MyAsset", "location"),
        }

    @pytest.mark.parametrize("existing, additional, expected", list(merge_importer_unhappy_test_cases()))
    def test_merge_importer_unhappy_path(
        self,
        existing: ImportedDataModel[UnverifiedDataModel],
        additional: ImportedDataModel[UnverifiedDataModel],
        expected: str,
    ) -> None:
        class DummyExistingFailing(BaseImporter):
            def to_data_model(self) -> ImportedDataModel[UnverifiedDataModel]:
                return existing

        class DummyAdditionalFailing(BaseImporter):
            def to_data_model(self) -> ImportedDataModel[UnverifiedDataModel]:
                return additional

        # Test with existing rules as None
        with pytest.raises(NeatError) as e:
            DMSMergeImporter(DummyExistingFailing(), DummyAdditionalFailing()).to_data_model()
        assert str(e.value) == expected
