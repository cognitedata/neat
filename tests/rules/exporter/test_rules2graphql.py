from pathlib import Path
import pytest

from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters
from cognite.neat.rules.exporter.rules2graphql import GraphQLSchemaExporter
import tempfile

def test_rules2graphql(simple_rules, grid_graphql_schema):
    file = tempfile.NamedTemporaryFile(suffix=".graphql")
    GraphQLSchemaExporter(rules=simple_rules, filepath=Path(file.name)).export()
    assert file.read().decode() == grid_graphql_schema



def test_raise_error10(transformation_rules):
    file = tempfile.NamedTemporaryFile(suffix=".graphql")
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        GraphQLSchemaExporter(rules=transformation_rules, filepath=Path(file.name)).export()
