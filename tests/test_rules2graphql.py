from cognite.neat.core.extractors.rules_to_graphql import rules2graphql_schema


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert rules2graphql_schema(simple_rules) == grid_graphql_schema
