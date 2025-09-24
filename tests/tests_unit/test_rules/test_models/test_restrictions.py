import pytest
from pydantic import ValidationError
from rdflib import XSD
from rdflib import Literal as RDFLiteral

from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities._restrictions import (
    ConceptPropertyCardinalityConstraint,
    ConceptPropertyValueConstraint,
    NamedIndividualEntity,
    parse_restriction,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import ConceptEntity
from cognite.neat.v0.core._issues.errors._general import NeatValueError


class TestConceptPropertyValueConstraint:
    @pytest.mark.parametrize(
        "data,expected_property,expected_constraint,expected_value_type",
        [
            ("valueConstraint:hasOwner(hasValue,ni:John)", "hasOwner", "hasValue", NamedIndividualEntity),
            ("valueConstraint:hasAge(hasValue,25^^integer)", "hasAge", "hasValue", RDFLiteral),
            ("valueConstraint:hasType(allValuesFrom,Vehicle)", "hasType", "allValuesFrom", ConceptEntity),
            ("valueConstraint:hasColor(someValuesFrom,Color)", "hasColor", "someValuesFrom", ConceptEntity),
            (
                "valueConstraint:has.complex_property-123(hasValue,test)",
                "has.complex_property-123",
                "hasValue",
                ConceptEntity,
            ),
        ],
    )
    def test_parse_value_constraints(self, data, expected_property, expected_constraint, expected_value_type):
        defaults = {"prefix": "ex"} if "Vehicle" in data or "Color" in data or "test" in data else {}
        result = ConceptPropertyValueConstraint._parse(data, defaults)

        assert result["property_"] == expected_property
        assert result["constraint"] == expected_constraint
        assert isinstance(result["value"], expected_value_type)

    def test_parse_named_individual_specific(self):
        data = "valueConstraint:hasOwner(hasValue,ni:John)"
        result = ConceptPropertyValueConstraint._parse(data, {})
        assert str(result["value"]) == "ni:John"

    def test_parse_datatype_specific(self):
        data = "valueConstraint:hasAge(hasValue,25^^integer)"
        result = ConceptPropertyValueConstraint.load(data)
        assert result.value.value == 25
        assert result.value.datatype == XSD.integer

    @pytest.mark.parametrize(
        "invalid_data,expected_error",
        [
            ("valueConstraint:hasAge(hasValue,25^^invalidtype)", "Invalid value format for datatype"),
            ("invalidConstraint:hasAge(hasValue,25)", "Invalid value constraint format"),
        ],
    )
    def test_parse_invalid_formats(self, invalid_data, expected_error):
        with pytest.raises(ValidationError, match=expected_error):
            ConceptPropertyValueConstraint.load(invalid_data)

    def test_comparison_less_than(self):
        """Test __lt__ comparison between restrictions."""
        restriction1 = ConceptPropertyValueConstraint.load("valueConstraint:hasAge(hasValue,25^^integer)")
        restriction2 = ConceptPropertyValueConstraint.load("valueConstraint:hasAge(hasValue,26^^integer)")

        # Compare based on property names (25 < 26)
        assert restriction1 < restriction2

    def test_comparison_equal(self):
        """Test __lt__ comparison between restrictions."""
        restriction1 = ConceptPropertyValueConstraint.load("valueConstraint:hasAge(hasValue,25^^integer)")
        restriction2 = ConceptPropertyValueConstraint.load("valueConstraint:hasAge(hasValue,25^^integer)")

        assert restriction1 == restriction2
        assert hash(restriction1) == hash(restriction2)

    def test_hash_consistency(self):
        """Test that hash is consistent with string representation."""
        restriction = ConceptPropertyValueConstraint.load("valueConstraint:hasOwner(hasValue,ni:John)")
        assert hash(restriction) == hash(str(restriction))

    def test_as_tuple(self):
        """Test as_tuple returns property and other fields as tuple."""
        restriction = ConceptPropertyValueConstraint.load("valueConstraint:hasOwner(hasValue,ni:John)")
        result = restriction.as_tuple()
        assert result[0] == "hasOwner"
        assert result[1] == "hasValue"
        assert result[2] == "ni:John"
        assert len(result) > 1
        assert all(item != "" for item in result)


class TestConceptPropertyCardinalityConstraint:
    @pytest.mark.parametrize(
        "data,expected_property,expected_constraint,expected_value,expected_on",
        [
            ("cardinalityConstraint:hasChild(minCardinality,2)", "hasChild", "minCardinality", 2, None),
            ("cardinalityConstraint:hasParent(maxCardinality,2)", "hasParent", "maxCardinality", 2, None),
            ("cardinalityConstraint:hasSpouse(cardinality,1)", "hasSpouse", "cardinality", 1, None),
            ("cardinalityConstraint:hasProperty(minCardinality,0)", "hasProperty", "minCardinality", 0, None),
            (
                "cardinalityConstraint:has.complex_property-123(maxCardinality,5)",
                "has.complex_property-123",
                "maxCardinality",
                5,
                None,
            ),
        ],
    )
    def test_parse_basic_cardinality_constraints(
        self, data, expected_property, expected_constraint, expected_value, expected_on
    ):
        result = ConceptPropertyCardinalityConstraint.load(data)

        assert result.property_ == expected_property
        assert result.constraint == expected_constraint
        assert result.value == expected_value
        assert result.on == expected_on
        assert str(result) == data

    @pytest.mark.parametrize(
        "data,expected_on_type",
        [
            ("cardinalityConstraint:hasAge(qualifiedCardinality,1,integer)", DataType),
            ("cardinalityConstraint:hasVehicle(qualifiedCardinality,3,Car)", ConceptEntity),
        ],
    )
    def test_parse_qualified_cardinality_constraints(self, data, expected_on_type):
        defaults = {"prefix": "ex"} if "Car" in data else {}
        result = ConceptPropertyCardinalityConstraint.load(data, **defaults)

        assert result.constraint == "qualifiedCardinality"
        assert isinstance(result.on, expected_on_type)

    def test_parse_invalid_cardinality_format(self):
        data = "invalidConstraint:hasProperty(minCardinality,1)"
        with pytest.raises(ValidationError, match="Invalid cardinality constraint format"):
            ConceptPropertyCardinalityConstraint.load(data)

    def test_comparison_less_than(self):
        """Test __lt__ comparison between restrictions."""
        restriction1 = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,18,integer)"
        )
        restriction2 = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,21,integer)"
        )
        # Compare based on property names (18 < 21)
        assert restriction1 < restriction2

    def test_comparison_equal(self):
        """Test __lt__ comparison between restrictions."""
        restriction1 = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,18,integer)"
        )
        restriction2 = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,18,integer)"
        )

        assert restriction1 == restriction2
        assert hash(restriction1) == hash(restriction2)

    def test_hash_consistency(self):
        """Test that hash is consistent with string representation."""
        restriction = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,18,integer)"
        )
        assert hash(restriction) == hash(str(restriction))

    def test_as_tuple(self):
        """Test as_tuple returns property and other fields as tuple."""
        restriction = ConceptPropertyCardinalityConstraint.load(
            "cardinalityConstraint:hasAge(qualifiedCardinality,18,integer)"
        )
        result = restriction.as_tuple()
        assert result[0] == "hasAge"
        assert result[1] == "qualifiedCardinality"
        assert result[2] == "18"
        assert result[3] == "integer"
        assert len(result) > 1
        assert all(item != "" for item in result)


class TestParseRestriction:
    @pytest.mark.parametrize(
        "data,expected_type,expected_property",
        [
            ("valueConstraint:hasOwner(hasValue,ni:John)", ConceptPropertyValueConstraint, "hasOwner"),
            ("cardinalityConstraint:hasChild(minCardinality,2)", ConceptPropertyCardinalityConstraint, "hasChild"),
            ("valueConstraint:hasType(allValuesFrom,Vehicle)", ConceptPropertyValueConstraint, "hasType"),
        ],
    )
    def test_parse_valid_restrictions(self, data, expected_type, expected_property):
        defaults = {"prefix": "test"} if "Vehicle" in data else {}
        result = parse_restriction(data, **defaults)

        assert isinstance(result, expected_type)
        assert result.property_ == expected_property

    @pytest.mark.parametrize(
        "invalid_data",
        [
            "invalidRestriction:hasProperty(someConstraint,value)",
            "",
        ],
    )
    def test_parse_invalid_restrictions(self, invalid_data):
        with pytest.raises(NeatValueError, match="Invalid restriction format"):
            parse_restriction(invalid_data)


class TestNamedIndividualEntity:
    def test_reset_prefix(self):
        entity = NamedIndividualEntity(suffix="test", prefix="one-that-gets-reset")
        assert entity.prefix == "ni"
