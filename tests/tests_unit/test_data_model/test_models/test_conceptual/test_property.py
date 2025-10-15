import pytest

from cognite.neat._data_model.models.conceptual._property import Property
from cognite.neat._data_model.models.entities import ConceptEntity, String
from cognite.neat._data_model.models.entities._data_types import Integer


class TestProperty:
    def test_property_min_max_count_validation_invalid(self) -> None:
        """Test that min_count > max_count raises ValidationError."""
        with pytest.raises(ValueError, match="min_count must be less than or equal to max_count"):
            Property(value_type=String(), min_count=5, max_count=2)

    def test_property_default_value_non_primitive_type(self) -> None:
        """Test that default value can only be set for primitive types."""
        concept_entity = ConceptEntity(prefix="ex", suffix="concept_1")
        with pytest.raises(ValueError, match="Setting default value is only supported for primitive value types"):
            Property(value_type=concept_entity, default="some_value")

    def test_property_default_value_list_not_supported(self) -> None:
        """Test that list default values are not supported."""
        with pytest.raises(ValueError, match="Setting list as default value is not supported"):
            Property(value_type=String(), default=["value1", "value2"])

    def test_property_default_value_multi_valued_property(self) -> None:
        """Test that default value cannot be set for multi-valued properties."""
        with pytest.raises(ValueError, match="Setting default value is only supported for single-valued properties"):
            Property(value_type=String(), min_count=2, default="value")

        with pytest.raises(ValueError, match="Setting default value is only supported for single-valued properties"):
            Property(value_type=String(), max_count=2, default="value")

    def test_property_default_value_type_mismatch(self) -> None:
        """Test that default value type must match property type."""
        with pytest.raises(ValueError, match="Default value type is .*, which does not match expected value type"):
            Property(value_type=Integer(), max_count=1, default="string_value")
