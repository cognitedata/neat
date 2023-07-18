from cognite.neat.core.rules.exporter.rules2graphql import rules2graphql_schema


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert rules2graphql_schema(simple_rules) == grid_graphql_schema
