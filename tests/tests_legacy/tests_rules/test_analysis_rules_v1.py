from cognite.neat.legacy.rules.analysis import (
    get_class_linkage,
    get_connected_classes,
    get_defined_classes,
    get_disconnected_classes,
    get_symmetric_pairs,
)


def test_rules_analysis(transformation_rules):
    rules = transformation_rules

    defined_classes = {
        "GeographicalRegion",
        "Orphanage",
        "RootCIMNode",
        "SubGeographicalRegion",
        "Substation",
        "Terminal",
    }

    assert get_defined_classes(rules) == defined_classes
    assert get_disconnected_classes(rules) == {"Orphanage"}

    defined_classes.remove("Orphanage")

    assert get_connected_classes(rules) == defined_classes
    assert get_symmetric_pairs(rules) == {("Substation", "Terminal"), ("Terminal", "Substation")}
    assert len(get_class_linkage(rules)) == 5
