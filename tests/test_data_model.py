from cognite.neat.core.rules import TransformationRules


def test_data_model(transformation_rules: TransformationRules):
    data_model = transformation_rules

    defined_classes = {
        "GeographicalRegion",
        "Orphanage",
        "RootCIMNode",
        "SubGeographicalRegion",
        "Substation",
        "Terminal",
    }

    assert data_model.get_defined_classes() == defined_classes
    assert data_model.get_disconnected_classes() == {"Orphanage"}
    defined_classes.remove("Orphanage")
    assert data_model.get_connected_classes() == defined_classes
    assert data_model.get_symmetric_pairs() == {("Substation", "Terminal"), ("Terminal", "Substation")}
    assert len(data_model.get_class_linkage()) == 5
