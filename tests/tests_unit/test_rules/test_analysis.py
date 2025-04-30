from cognite.neat.core._data_model.analysis import RulesAnalysis
from cognite.neat.core._data_model.models import ConceptualDataModel
from cognite.neat.core._data_model.models.conceptual import (
    ConceptualUnvalidatedConcept,
    ConceptualUnvalidatedDataModel,
    ConceptualUnvalidatedMetadata,
    ConceptualUnvalidatedProperty,
)


class TestRulesAnalysis:
    def test_class_parent_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).parents_by_class()) == 26

    def test_classes_with_properties(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).properties_by_class()) == 20

    def test_class_property_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).properties_by_id_by_class()) == 20

    def test_defined_classes(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).defined_classes(include_ancestors=False)) == 20
        assert len(RulesAnalysis(david_rules).defined_classes(include_ancestors=True)) == 26

    def test_get_class_linkage(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).class_linkage(include_ancestors=False)) == 28
        assert len(RulesAnalysis(david_rules).class_linkage(include_ancestors=True)) == 57

    def test_symmetric_pairs(self, david_rules: ConceptualDataModel) -> None:
        assert len(RulesAnalysis(david_rules).symmetrically_connected_classes(include_ancestors=True)) == 0
        assert len(RulesAnalysis(david_rules).symmetrically_connected_classes(include_ancestors=False)) == 0


class TestAnalysis:
    def test_parents_by_class(self) -> None:
        generation = ConceptualUnvalidatedDataModel(
            metadata=ConceptualUnvalidatedMetadata(
                "my_space",
                "my_external_id",
                "v1",
                "doctrino",
            ),
            properties=[
                ConceptualUnvalidatedProperty("child", "childProp", "string"),
                ConceptualUnvalidatedProperty("parent", "parentProp", "string"),
                ConceptualUnvalidatedProperty("grandparent", "grandparentProp", "string"),
            ],
            concepts=[
                ConceptualUnvalidatedConcept("child", implements="parent"),
                ConceptualUnvalidatedConcept("parent", implements="grandparent"),
                ConceptualUnvalidatedConcept("grandparent", implements=None),
            ],
        )

        explore = RulesAnalysis(generation.as_verified_data_model(), None)

        parents_by_class = explore.parents_by_class(include_ancestors=True)
        assert {
            class_.suffix: {parent.suffix for parent in parents} for class_, parents in parents_by_class.items()
        } == {
            "child": {"parent", "grandparent"},
            "parent": {"grandparent"},
            "grandparent": set(),
        }

        parents_by_class = explore.parents_by_class(include_ancestors=False)
        assert {
            class_.suffix: {parent.suffix for parent in parents} for class_, parents in parents_by_class.items()
        } == {
            "child": {"parent"},
            "parent": {"grandparent"},
            "grandparent": set(),
        }
