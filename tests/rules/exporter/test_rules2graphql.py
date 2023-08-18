import pytest
from cognite.neat.rules.exporter.rules2graphql import GraphQLSchema
from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert GraphQLSchema.from_rules(transformation_rules=simple_rules).schema == grid_graphql_schema


def test_raise_error10(transformation_rules):
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        _ = GraphQLSchema.from_rules(transformation_rules=transformation_rules).schema
