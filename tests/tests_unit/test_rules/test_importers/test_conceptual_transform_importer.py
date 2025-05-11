from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.importers import BaseImporter, ConceptualTransformImporter
from cognite.neat.core._data_model.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
)
from cognite.neat.core._data_model.transformers import ToDMSCompliantEntities


class DummyImporter(BaseImporter[InformationInputRules]):
    def to_rules(self) -> ReadRules[InformationInputRules]:
        return ReadRules(
            InformationInputRules(
                metadata=InformationInputMetadata("my_space", "my_model", "v1", "me"),
                classes=[InformationInputClass("MyClass")],
                properties=[InformationInputProperty("MyClass", "my_##_property", "text", max_count=1)],
            ),
            {},
        )


class TestConceptualTransformImporter:
    def test_import_transform(self) -> None:
        importer = ConceptualTransformImporter(DummyImporter(), [ToDMSCompliantEntities(always_standardize=True)])

        rules = importer.to_rules()

        assert isinstance(rules.rules, InformationInputRules)
        properties = rules.rules.properties
        assert len(properties) == 1
        assert properties[0].property_ == "myProperty"
