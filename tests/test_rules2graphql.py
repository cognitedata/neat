from cognite.neat.core.rules.exporter.rules2graphql import GraphQLSchema


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert GraphQLSchema(transformation_rules=simple_rules).schema == grid_graphql_schema
