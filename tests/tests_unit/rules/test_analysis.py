from cognite.neat.rules._analysis._information_rules import InformationArchitectRulesAnalysis
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules._types import ClassEntity


class TestRulesAnalysis:
    def test_class_parent_pairs(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).class_parent_pairs()) == 26

    def test_classes_with_properties(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).classes_with_properties()) == 20

    def test_class_property_pairs(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).class_property_pairs()) == 20

    def test_defined_classes(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).defined_classes(consider_inheritance=False)) == 20
        assert len(InformationArchitectRulesAnalysis(david_rules).defined_classes(consider_inheritance=True)) == 26

    def test_disconnected_classes(self, david_rules: InformationRules) -> None:
        assert InformationArchitectRulesAnalysis(david_rules).disconnected_classes(consider_inheritance=False) == {
            ClassEntity.from_raw("power:GeoLocation")
        }

    def test_connected_classes(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).connected_classes(consider_inheritance=False)) == 24
        assert len(InformationArchitectRulesAnalysis(david_rules).connected_classes(consider_inheritance=True)) == 25

    def test_get_class_linkage(self, david_rules: InformationRules) -> None:
        assert len(InformationArchitectRulesAnalysis(david_rules).class_linkage(consider_inheritance=False)) == 28
        assert len(InformationArchitectRulesAnalysis(david_rules).class_linkage(consider_inheritance=True)) == 63

    def test_symmetric_pairs(self, david_rules: InformationRules) -> None:
        assert (
            len(
                InformationArchitectRulesAnalysis(david_rules).symmetrically_connected_classes(
                    consider_inheritance=True
                )
            )
            == 0
        )
        assert (
            len(
                InformationArchitectRulesAnalysis(david_rules).symmetrically_connected_classes(
                    consider_inheritance=False
                )
            )
            == 0
        )

    def test_subset_rules(self, david_rules: InformationRules) -> None:
        assert InformationArchitectRulesAnalysis(david_rules).subset_rules(
            {ClassEntity.from_raw("power:GeoLocation")}
        ).classes.data[0].class_ == ClassEntity.from_raw("power:GeoLocation")
        assert (
            len(
                InformationArchitectRulesAnalysis(david_rules)
                .subset_rules({ClassEntity.from_raw("power:GeoLocation")})
                .classes.data
            )
            == 1
        )
