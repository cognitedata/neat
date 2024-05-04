from cognite.neat.legacy.rules.models.rules import Rules


def test_extra_triples(transformation_rules: Rules):
    assert len(transformation_rules.instances) == 11
