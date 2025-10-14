import pytest

from cognite.neat.v0.core._data_model.models.entities import ContainerConstraintEntity, ContainerEntity
from cognite.neat.v0.core._data_model.models.physical._unverified import _parse_constraints


class TestParseConstraints:
    def test_parse_constraints_none(self):
        """Test that None input returns None."""
        result = _parse_constraints(None)
        assert result is None

    def test_parse_constraints_single_entity(self):
        """Test parsing a single ContainerConstraintEntity."""
        constraint = ContainerConstraintEntity(prefix="uniqueness", suffix="name")
        result = _parse_constraints(constraint)
        assert result == [constraint]

    def test_parse_constraints_single_string(self):
        """Test parsing a single string constraint."""
        result = _parse_constraints("uniqueness:name")
        assert len(result) == 1
        assert isinstance(result[0], ContainerConstraintEntity)
        assert result[0].prefix == "uniqueness"
        assert result[0].suffix == "name"

    def test_parse_constraints_single_string_with_container(self):
        """Test parsing a single string constraint with container specification."""
        result = _parse_constraints("requires:my_space_Asset(require=my_space:Asset)", default_space="default_space")
        assert len(result) == 1
        assert isinstance(result[0], ContainerConstraintEntity)
        assert result[0].prefix == "requires"
        assert result[0].suffix == "my_space_Asset"
        assert isinstance(result[0].require, ContainerEntity)

    def test_parse_constraints_comma_separated_string(self):
        """Test parsing comma-separated string constraints."""
        result = _parse_constraints("uniqueness:name, requires:asset")
        assert len(result) == 2
        assert all(isinstance(c, ContainerConstraintEntity) for c in result)
        assert result[0].prefix == "uniqueness"
        assert result[0].suffix == "name"
        assert result[1].prefix == "requires"
        assert result[1].suffix == "asset"

    def test_parse_constraints_comma_separated_string_with_empty_items(self):
        """Test parsing comma-separated string with empty items."""
        result = _parse_constraints("uniqueness:name, , requires:asset,  ")
        assert len(result) == 2
        assert result[0].prefix == "uniqueness"
        assert result[0].suffix == "name"
        assert result[1].prefix == "requires"
        assert result[1].suffix == "asset"

    def test_parse_constraints_list_of_entities(self):
        """Test parsing a list of ContainerConstraintEntity objects."""
        constraints = [
            ContainerConstraintEntity(prefix="uniqueness", suffix="name"),
            ContainerConstraintEntity(prefix="requires", suffix="asset"),
        ]
        result = _parse_constraints(constraints)
        assert result == constraints

    def test_parse_constraints_list_of_strings(self):
        """Test parsing a list of string constraints."""
        constraints = ["uniqueness:name", "requires:asset"]
        result = _parse_constraints(constraints)
        assert len(result) == 2
        assert all(isinstance(c, ContainerConstraintEntity) for c in result)
        assert result[0].prefix == "uniqueness"
        assert result[0].suffix == "name"
        assert result[1].prefix == "requires"
        assert result[1].suffix == "asset"

    def test_parse_constraints_mixed_list(self):
        """Test parsing a list with mixed ContainerConstraintEntity and string types."""
        entity = ContainerConstraintEntity(prefix="uniqueness", suffix="name")
        constraints = [entity, "requires:asset"]
        result = _parse_constraints(constraints)
        assert len(result) == 2
        assert result[0] == entity
        assert isinstance(result[1], ContainerConstraintEntity)
        assert result[1].prefix == "requires"
        assert result[1].suffix == "asset"

    def test_parse_constraints_list_with_comma_separated_strings(self):
        """Test parsing a list containing comma-separated strings."""
        constraints = ["uniqueness:name, requires:asset", "another:constraint"]
        result = _parse_constraints(constraints)
        assert len(result) == 3
        assert result[0].prefix == "uniqueness"
        assert result[0].suffix == "name"
        assert result[1].prefix == "requires"
        assert result[1].suffix == "asset"
        # when not possible to process it it will return as is
        assert result[2] == "another:constraint"

    def test_parse_constraints_with_default_space(self):
        """Test parsing constraints with default_space parameter."""
        result = _parse_constraints("uniqueness:name", default_space="test_space")
        assert len(result) == 1
        assert isinstance(result[0], ContainerConstraintEntity)

    def test_parse_constraints_invalid_list_item_type(self):
        """Test that invalid types in list raise TypeError."""
        with pytest.raises(TypeError, match="Unexpected type for constraint"):
            _parse_constraints([123])  # Invalid type in list

    def test_parse_constraints_invalid_type(self):
        """Test that invalid constraint type raises TypeError."""
        with pytest.raises(TypeError, match="Unexpected type for constraint"):
            _parse_constraints(123)  # Invalid type
