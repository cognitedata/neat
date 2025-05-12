from cognite.neat.core._data_model.models.conceptual import (
    UnverifiedConceptualClass,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.core._data_model.transformers import ConceptualPropertyRenaming
from cognite.neat.core._issues import catch_warnings


class TestConceptualPropertyRenaming:
    def test_conceptual_property_renaming(self) -> None:
        input_model = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "me"),
            properties=[
                UnverifiedConceptualProperty("Asset", "parent", "Asset", min_count=0, max_count=1),
                UnverifiedConceptualProperty("Asset", "name", "text", min_count=0, max_count=1),
            ],
            classes=[UnverifiedConceptualClass("Asset")],
        ).as_verified_rules()

        with catch_warnings() as issues:
            mapped = ConceptualPropertyRenaming(
                {
                    ("Asset", "parent"): ("Asset", "asset_parent"),
                    ("Asset", "does_not_exist"): ("Asset", "asset_does_not_exist"),
                }
            ).transform(input_model)

        assert len(issues) == 1
        assert issues[0].message == "Property 'does_not_exist' not found in class 'Asset'."
        assert mapped.properties[0].property_ == "asset_parent"
