import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.entities._base import ConceptEntity, Entity, UnknownEntity
from cognite.neat._data_model.models.entities._constants import Undefined, Unknown


class SubEntity(Entity): ...


class TestEntity:
    def test_entity_creation_with_suffix_only(self) -> None:
        entity = Entity(suffix="TestSuffix")
        assert entity.suffix == "TestSuffix"
        assert entity.prefix == Undefined
        assert entity.as_tuple() == ("TestSuffix",)
        assert repr(entity) == "Entity(prefix=_UndefinedType(),suffix='TestSuffix')"

    def test_entity_creation_with_prefix_and_suffix(self) -> None:
        entity = Entity(prefix="test", suffix="TestSuffix")
        assert entity.prefix == "test"
        assert entity.suffix == "TestSuffix"
        assert str(entity) == "test:TestSuffix"
        assert repr(entity) == "Entity(prefix='test',suffix='TestSuffix')"
        assert entity.as_tuple() == ("test", "TestSuffix")

    def test_entity_equality(self) -> None:
        entity1 = Entity(prefix="test", suffix="TestSuffix")
        entity2 = Entity(prefix="test", suffix="TestSuffix")
        entity3 = Entity(prefix="other", suffix="TestSuffix")

        assert entity1 == entity2
        assert entity1 != entity3

    def test_entity_ordering(self) -> None:
        entity1 = Entity(prefix="a", suffix="TestSuffix")
        entity2 = Entity(prefix="b", suffix="TestSuffix")
        entity3 = Entity(prefix="a", suffix="ZTestSuffix")

        assert entity1 < entity2
        assert entity1 < entity3

    def test_entity_hash(self) -> None:
        entity1 = Entity(prefix="test", suffix="TestSuffix")
        entity2 = Entity(prefix="test", suffix="TestSuffix")

        assert hash(entity1) == hash(entity2)

    def test_entity_hash_subclassing(self) -> None:
        entity1 = Entity(prefix="test", suffix="TestSuffix")
        entity2 = SubEntity(prefix="test", suffix="TestSuffix")

        assert hash(entity1) != hash(entity2)

    def test_strip_string_validation(self) -> None:
        entity = Entity(prefix="  test  ", suffix="  TestSuffix  ")
        assert entity.prefix == "test"
        assert entity.suffix == "TestSuffix"

    @pytest.mark.parametrize(
        "invalid_prefix",
        [
            "1prefix",  # starts with number
            "",  # too short when combined
            "a" * 44,  # too long
            "prefix@",  # invalid character
        ],
    )
    def test_invalid_prefix_patterns(self, invalid_prefix: str) -> None:
        with pytest.raises(ValidationError):
            Entity(prefix=invalid_prefix, suffix="valid")

    @pytest.mark.parametrize(
        "invalid_suffix",
        [
            "",  # empty
            "a" * 256,  # too long
            "invalid space",  # contains space
        ],
    )
    def test_invalid_suffix_patterns(self, invalid_suffix: str) -> None:
        with pytest.raises(ValidationError):
            Entity(suffix=invalid_suffix)


class TestConceptEntity:
    def test_concept_entity_creation(self) -> None:
        entity = ConceptEntity(suffix="TestSuffix", version="1.0")
        assert entity.suffix == "TestSuffix"
        assert entity.version == "1.0"

    def test_concept_entity_string_representation_with_version(self) -> None:
        entity = ConceptEntity(prefix="test", suffix="TestSuffix", version="1.0")
        assert str(entity) == "test:TestSuffix(version=1.0)"

    def test_concept_entity_without_version(self) -> None:
        entity = ConceptEntity(suffix="TestSuffix")
        assert entity.version is None
        assert str(entity) == "TestSuffix"


class TestUnknownEntity:
    def test_unknown_entity_creation(self) -> None:
        entity = UnknownEntity()
        assert entity.prefix == Undefined
        assert entity.suffix == Unknown

    def test_unknown_entity_id_property(self) -> None:
        entity = UnknownEntity()
        assert entity.id == str(Unknown)

    def test_unknown_entity_string_representation(self) -> None:
        entity = UnknownEntity()
        assert str(entity) == str(Unknown)


class TestEntityComparison:
    def test_different_entity_types_not_equal(self) -> None:
        entity = Entity(suffix="test")
        concept_entity = ConceptEntity(suffix="test")

        with pytest.raises(TypeError):
            assert entity == concept_entity

    def test_entity_ordering_different_types(self) -> None:
        entity = Entity(suffix="test")
        concept_entity = ConceptEntity(suffix="test")

        with pytest.raises(TypeError):
            assert entity < concept_entity
