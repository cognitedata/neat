from cognite.neat.core.rules.models import TransformationRules


def test_extra_triples(transformation_rules: TransformationRules):
    assert len(transformation_rules.instances) == 11
