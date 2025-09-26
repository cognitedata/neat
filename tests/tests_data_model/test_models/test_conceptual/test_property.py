from datetime import date

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.conceptual._properties import Property
from cognite.neat._data_model.models.entities import URI, ConceptEntity, String, UnknownEntity
from cognite.neat._data_model.models.entities._data_types import AnyURI, Boolean, Date, Float, Integer


class TestProperty:
    def test_property_creation_with_valid_data(self):
        """Test creating a Property with valid data."""
        property_obj = Property(
            value_type=String(),
            min_count=1,
            max_count=5,
        )

        assert isinstance(property_obj.value_type, String)
        assert property_obj.min_count == 1
        assert property_obj.max_count == 5

    def test_property_with_concept_entity_value_type(self):
        """Test creating a Property with ConceptEntity as value type."""
        concept_entity = ConceptEntity(prefix="ex", suffix="concept_1")
        property_obj = Property(value_type=concept_entity)

        assert property_obj.value_type == concept_entity

    def test_property_with_unknown_entity_value_type(self):
        """Test creating a Property with UnknownEntity as value type."""
        property_obj = Property(value_type=UnknownEntity())

        assert isinstance(property_obj.value_type, UnknownEntity)

    def test_property_with_instance_reference(self):
        """Test creating a Property with instance reference."""
        uri1 = URI("http://example.com/instance1")
        uri2 = URI("http://example.com/instance2")

        property_obj = Property(value_type=String(), instance_reference=[uri1, uri2])

        assert property_obj.instance_reference == [uri1, uri2]

    def test_property_max_count_validation_zero(self):
        """Test that max_count must be >= 0."""
        with pytest.raises(ValidationError):
            Property(value_type=String(), max_count=-1)

    def test_property_min_max_count_validation_valid(self):
        """Test that min_count <= max_count passes validation."""
        property_obj = Property(value_type=String(), min_count=2, max_count=5)

        assert property_obj.min_count == 2
        assert property_obj.max_count == 5

    def test_property_min_max_count_validation_equal(self):
        """Test that min_count == max_count passes validation."""
        property_obj = Property(value_type=String(), min_count=3, max_count=3)

        assert property_obj.min_count == 3
        assert property_obj.max_count == 3

    def test_property_min_max_count_validation_invalid(self):
        """Test that min_count > max_count raises ValidationError."""
        with pytest.raises(ValueError, match="min_count must be less than or equal to max_count"):
            Property(value_type=String(), min_count=5, max_count=2)

    def test_property_defaults(self):
        """Test Property with default values."""
        property_obj = Property(value_type=String())

        assert property_obj.min_count is None
        assert property_obj.max_count is None
        assert property_obj.default is None
        assert property_obj.instance_reference is None

    def test_property_default_value_non_primitive_type(self):
        """Test that default value can only be set for primitive types."""
        concept_entity = ConceptEntity(prefix="ex", suffix="concept_1")
        with pytest.raises(ValueError, match="Setting default value is only supported for primitive value types"):
            Property(value_type=concept_entity, default="some_value")

    def test_property_default_value_list_not_supported(self):
        """Test that list default values are not supported."""
        with pytest.raises(ValueError, match="Setting list as default value is not supported"):
            Property(value_type=String(), default=["value1", "value2"])

    def test_property_default_value_multi_valued_property(self):
        """Test that default value cannot be set for multi-valued properties."""
        with pytest.raises(ValueError, match="Setting default value is only supported for single-valued properties"):
            Property(value_type=String(), min_count=2, default="value")

        with pytest.raises(ValueError, match="Setting default value is only supported for single-valued properties"):
            Property(value_type=String(), max_count=2, default="value")

    def test_property_default_value_type_mismatch(self):
        """Test that default value type must match property type."""
        with pytest.raises(ValueError, match="Default value type is .*, which does not match expected value type"):
            Property(value_type=Integer(), max_count=1, default="string_value")

    def test_property_with_different_data_types(self):
        """Test creating Properties with different DataType subclasses."""
        # Test Integer
        int_property = Property(value_type=Integer(), max_count=1, default=42)
        assert isinstance(int_property.value_type, Integer)
        assert int_property.default == 42

        # Test Boolean
        bool_property = Property(value_type=Boolean(), max_count=1, default=True)
        assert isinstance(bool_property.value_type, Boolean)
        assert bool_property.default is True

        # Test Float
        float_property = Property(value_type=Float(), max_count=1, default=3.14)
        assert isinstance(float_property.value_type, Float)
        assert float_property.default == 3.14

        # Test Date
        date_property = Property(value_type=Date(), max_count=1, default=date(2020, 1, 1))
        assert isinstance(date_property.value_type, Date)

        # Test AnyURI
        uri_property = Property(value_type=AnyURI())
        assert isinstance(uri_property.value_type, AnyURI)
