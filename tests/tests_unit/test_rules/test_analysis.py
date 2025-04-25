from cognite.neat.core._rules.analysis import RulesAnalysis
from cognite.neat.core._rules.models import InformationRules
from cognite.neat.core._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
)


class TestRulesAnalysis:
    def test_class_parent_pairs(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).parents_by_class()) == 26

    def test_classes_with_properties(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).properties_by_class()) == 20

    def test_class_property_pairs(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).properties_by_id_by_class()) == 20

    def test_defined_classes(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).defined_classes(include_ancestors=False)) == 20
        assert len(RulesAnalysis(david_rules).defined_classes(include_ancestors=True)) == 26

    def test_get_class_linkage(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).class_linkage(include_ancestors=False)) == 28
        assert len(RulesAnalysis(david_rules).class_linkage(include_ancestors=True)) == 57

    def test_symmetric_pairs(self, david_rules: InformationRules) -> None:
        assert len(RulesAnalysis(david_rules).symmetrically_connected_classes(include_ancestors=True)) == 0
        assert len(RulesAnalysis(david_rules).symmetrically_connected_classes(include_ancestors=False)) == 0


class TestAnalysis:
    def test_parents_by_class(self) -> None:
        generation = InformationInputRules(
            metadata=InformationInputMetadata(
                "my_space",
                "my_external_id",
                "v1",
                "doctrino",
            ),
            properties=[
                InformationInputProperty("child", "childProp", "string"),
                InformationInputProperty("parent", "parentProp", "string"),
                InformationInputProperty("grandparent", "grandparentProp", "string"),
            ],
            classes=[
                InformationInputClass("child", implements="parent"),
                InformationInputClass("parent", implements="grandparent"),
                InformationInputClass("grandparent", implements=None),
            ],
        )

        explore = RulesAnalysis(generation.as_verified_rules(), None)

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
