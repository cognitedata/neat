from cognite.neat.rules._analysis import (
    get_class_linkage,
    get_connected_classes,
    get_defined_classes,
    get_disconnected_classes,
    get_symmetric_pairs,
)
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules._types import ClassEntity


class TestRulesAnalysis:
    def test_defined_classes(self, david_rules: InformationRules) -> None:
        assert len(get_defined_classes(david_rules, consider_inheritance=False)) == 20
        assert len(get_defined_classes(david_rules, consider_inheritance=True)) == 26

    def test_disconnected_classes(self, david_rules: InformationRules) -> None:
        assert get_disconnected_classes(david_rules, consider_inheritance=False) == {
            ClassEntity.from_raw("power:GeoLocation")
        }

    def test_connected_classes(self, david_rules: InformationRules) -> None:
        assert len(get_connected_classes(david_rules, consider_inheritance=False)) == 24
        assert len(get_connected_classes(david_rules, consider_inheritance=True)) == 25

    def test_get_class_linkage(self, david_rules: InformationRules) -> None:
        assert len(get_class_linkage(david_rules, consider_inheritance=False)) == 28
        assert len(get_class_linkage(david_rules, consider_inheritance=True)) == 63

    def test_symmetric_pairs(self, david_rules: InformationRules) -> None:
        assert len(get_symmetric_pairs(david_rules, consider_inheritance=True)) == 0
        assert len(get_symmetric_pairs(david_rules, consider_inheritance=False)) == 0
