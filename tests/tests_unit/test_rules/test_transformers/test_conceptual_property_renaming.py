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
                UnverifiedConceptualProperty("Asset", "tags", "text", min_count=0, max_count=100),
            ],
            classes=[UnverifiedConceptualClass("Asset")],
        ).as_verified_rules()

        with catch_warnings() as issues:
            mapped = ConceptualPropertyRenaming(
                {
                    ("Asset", "parent"): ("Asset", "asset_parent"),
                    ("Asset", "does_not_exist"): ("Asset", "asset_does_not_exist"),
                    ("DoesNotExist", "parent"): ("Asset", "asset_parent"),
                    ("Asset", "tags"): ("Asset", "parent"),
                    ("Asset", "name"): ("DoesNotExistEither", "name"),
                }
            ).transform(input_model)

        assert len(issues) == 4
        assert {str(issue) for issue in issues} == {
            "NeatValueWarning: Property 'does_not_exist' not found in concept 'Asset'.",
            "NeatValueWarning: Concept 'DoesNotExist' not found in data model.",
            "NeatValueWarning: Concept 'DoesNotExistEither' not found in data model.",
            "NeatValueWarning: Property 'parent' already exists in concept 'Asset'.",
        }
        assert mapped.properties[0].property_ == "asset_parent"
