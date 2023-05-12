from cognite.neat.core.extractors.transformation_rules_to_graphql import rules2graphql


def test_rules2graphql(simple_rules, graphql_schema):
    assert rules2graphql(simple_rules) == graphql_schema
