from cognite.neat._rules.analysis import InformationAnalysis, RuleAnalysis
from cognite.neat._rules.models import InformationRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
)


class TestInformationRulesAnalysis:
    def test_class_parent_pairs(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).class_parent_pairs()) == 26

    def test_classes_with_properties(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).classes_with_properties()) == 20

    def test_class_property_pairs(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).class_property_pairs()) == 20

    def test_defined_classes(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).defined_classes(consider_inheritance=False)) == 20
        assert len(InformationAnalysis(david_rules).defined_classes(consider_inheritance=True)) == 26

    def test_disconnected_classes(self, david_rules: InformationRules) -> None:
        assert InformationAnalysis(david_rules).disconnected_classes(consider_inheritance=False) == {
            ClassEntity.load("power:GeoLocation")
        }

    def test_connected_classes(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).connected_classes(consider_inheritance=False)) == 24
        assert len(InformationAnalysis(david_rules).connected_classes(consider_inheritance=True)) == 25

    def test_get_class_linkage(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).class_linkage(consider_inheritance=False)) == 28
        assert len(InformationAnalysis(david_rules).class_linkage(consider_inheritance=True)) == 63

    def test_symmetric_pairs(self, david_rules: InformationRules) -> None:
        assert len(InformationAnalysis(david_rules).symmetrically_connected_classes(consider_inheritance=True)) == 0
        assert len(InformationAnalysis(david_rules).symmetrically_connected_classes(consider_inheritance=False)) == 0

    def test_subset_rules(self, david_rules: InformationRules) -> None:
        assert InformationAnalysis(david_rules).subset_rules({ClassEntity.load("power:GeoLocation")}).classes[
            0
        ].class_ == ClassEntity.load("power:GeoLocation")
        assert len(InformationAnalysis(david_rules).subset_rules({ClassEntity.load("power:GeoLocation")}).classes) == 1


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

        explore = RuleAnalysis(generation.as_verified_rules(), None)

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
