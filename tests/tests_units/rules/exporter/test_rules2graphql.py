from pathlib import Path

import pytest

from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters
from cognite.neat.rules.exporter._rules2graphql import GraphQLSchemaExporter


def test_rules2graphql(simple_rules, grid_graphql_schema, tmp_path: Path):
    filepath = tmp_path / "test.graphql"
    GraphQLSchemaExporter(rules=simple_rules).export_to_file(filepath)
    assert filepath.read_text() == grid_graphql_schema


def test_raise_error10(transformation_rules, tmp_path: Path):
    filepath = tmp_path / "test.graphql"
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        GraphQLSchemaExporter(rules=transformation_rules).export_to_file(filepath=filepath)
