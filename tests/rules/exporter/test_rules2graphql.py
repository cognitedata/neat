import pytest

from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters
from cognite.neat.rules.exporter.rules2graphql import GraphQLSchemaExporter


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert GraphQLSchemaExporter(rules=simple_rules, filepath=None).data == grid_graphql_schema


def test_raise_error10(transformation_rules):
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        GraphQLSchemaExporter(rules=transformation_rules, filepath=None)
