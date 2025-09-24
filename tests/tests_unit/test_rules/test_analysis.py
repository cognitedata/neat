from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.models import ConceptualDataModel
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)


class TestRulesAnalysis:
    def test_class_parent_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).parents_by_concept()) == 26

    def test_classes_with_properties(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).properties_by_concepts()) == 20

    def test_class_property_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).properties_by_id_by_concept()) == 20

    def test_defined_classes(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).defined_concepts(include_ancestors=False)) == 20
        assert len(DataModelAnalysis(david_rules).defined_concepts(include_ancestors=True)) == 26

    def test_get_class_linkage(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).concept_linkage(include_ancestors=False)) == 28
        assert len(DataModelAnalysis(david_rules).concept_linkage(include_ancestors=True)) == 57

    def test_symmetric_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(DataModelAnalysis(david_rules).symmetrically_connected_concepts(include_ancestors=True)) == 0
        assert len(DataModelAnalysis(david_rules).symmetrically_connected_concepts(include_ancestors=False)) == 0


class TestAnalysis:
    def test_parents_by_class(self) -> None:
        generation = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata(
                "my_space",
                "my_external_id",
                "v1",
                "doctrino",
            ),
            properties=[
                UnverifiedConceptualProperty("child", "childProp", "string"),
                UnverifiedConceptualProperty("parent", "parentProp", "string"),
                UnverifiedConceptualProperty("grandparent", "grandparentProp", "string"),
            ],
            concepts=[
                UnverifiedConcept("child", implements="parent"),
                UnverifiedConcept("parent", implements="grandparent"),
                UnverifiedConcept("grandparent", implements=None),
            ],
        )

        explore = DataModelAnalysis(generation.as_verified_data_model(), None)

        parents_by_class = explore.parents_by_concept(include_ancestors=True)
        assert {
            class_.suffix: {parent.suffix for parent in parents} for class_, parents in parents_by_class.items()
        } == {
            "child": {"parent", "grandparent"},
            "parent": {"grandparent"},
            "grandparent": set(),
        }

        parents_by_class = explore.parents_by_concept(include_ancestors=False)
        assert {
            class_.suffix: {parent.suffix for parent in parents} for class_, parents in parents_by_class.items()
        } == {
            "child": {"parent"},
            "parent": {"grandparent"},
            "grandparent": set(),
        }
