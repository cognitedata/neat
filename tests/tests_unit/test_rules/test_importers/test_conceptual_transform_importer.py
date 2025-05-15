from cognite.neat.core._data_model._shared import ImportedDataModel
from cognite.neat.core._data_model.importers import BaseImporter, ConceptualTransformImporter
from cognite.neat.core._data_model.models.conceptual import (
    UnverifiedConceptualClass,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.core._data_model.transformers import ToDMSCompliantEntities


class DummyImporter(BaseImporter[UnverifiedConceptualDataModel]):
    def to_rules(self) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        return ImportedDataModel(
            UnverifiedConceptualDataModel(
                metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "me"),
                classes=[UnverifiedConceptualClass("MyClass")],
                properties=[UnverifiedConceptualProperty("MyClass", "my_##_property", "text", max_count=1)],
            ),
            {},
        )


class TestConceptualTransformImporter:
    def test_import_transform(self) -> None:
        importer = ConceptualTransformImporter(DummyImporter(), [ToDMSCompliantEntities(always_standardize=True)])

        rules = importer.to_rules()

        assert isinstance(rules.rules, UnverifiedConceptualDataModel)
        properties = rules.rules.properties
        assert len(properties) == 1
        assert properties[0].property_ == "myProperty"
