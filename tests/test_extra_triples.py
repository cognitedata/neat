from cognite.neat.core.rules import TransformationRules


def test_extra_triples(transformation_rules: TransformationRules):
    assert len(transformation_rules.instances) == 11
