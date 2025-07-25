from collections.abc import Iterable

import pytest
from rdflib import URIRef

from cognite.neat.core._data_model.models import SheetList
from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.conceptual import (
    Concept,
    ConceptualProperty,
    UnverifiedConcept,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._data_model.models.entities import ConceptEntity, MultiValueTypeInfo, UnknownEntity
from cognite.neat.core._data_model.transformers import UnionConceptualDataModel


def merge_model_test_cases() -> Iterable:
    metadata = UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino")

    single_cls1 = UnverifiedConceptualDataModel(
        metadata=metadata,
        concepts=[UnverifiedConcept("PrimaryClass")],
        properties=[UnverifiedConceptualProperty("PrimaryClass", "primary_property", "text")],
    )
    single_cls2 = UnverifiedConceptualDataModel(
        metadata=metadata,
        concepts=[UnverifiedConcept("SecondaryClass")],
        properties=[UnverifiedConceptualProperty("SecondaryClass", "secondary_property", "text")],
    )
    combined = UnverifiedConceptualDataModel(
        metadata=metadata,
        concepts=[UnverifiedConcept("PrimaryClass"), UnverifiedConcept("SecondaryClass")],
        properties=[
            UnverifiedConceptualProperty("PrimaryClass", "primary_property", "text"),
            UnverifiedConceptualProperty("SecondaryClass", "secondary_property", "text"),
        ],
    )

    yield pytest.param(
        single_cls1,
        single_cls2,
        {"join": "primary", "priority": "primary", "conflict_resolution": "priority"},
        single_cls1,
        id="Merge with primary only",
    )
    yield pytest.param(
        single_cls1,
        single_cls2,
        {"join": "secondary", "priority": "primary", "conflict_resolution": "priority"},
        single_cls2,
        id="Merge with secondary only",
    )
    yield pytest.param(
        single_cls1,
        single_cls2,
        {"join": "combined", "priority": "primary", "conflict_resolution": "priority"},
        combined,
        id="Merge with combined",
    )


def merge_properties_test_cases() -> Iterable:
    cls_ = ConceptEntity.load("my_space:Car")
    first = ConceptualProperty(concept=cls_, property_="my_property", value_type=dt.String(), min_count=0, max_count=1)
    second = ConceptualProperty(
        concept=cls_,
        property_="my_property",
        value_type=dt.Integer(),
        min_count=0,
        max_count=5,
        instance_source=[URIRef("my_source")],
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        ConceptualProperty(
            concept=cls_,
            property_="my_property",
            value_type=dt.String(),
            min_count=0,
            max_count=1,
            instance_source=[URIRef("my_source")],
        ),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        ConceptualProperty(
            concept=cls_,
            property_="my_property",
            value_type=MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
            min_count=0,
            max_count=5,
            instance_source=[URIRef("my_source")],
        ),
        id="Merge with combined",
    )


def merge_classes_test_cases() -> Iterable:
    cls_ = ConceptEntity.load("my_space:Car")
    first = Concept(concept=cls_, implements=[ConceptEntity.load("my_space:Vehicle")])
    second = Concept(
        concept=cls_, implements=[ConceptEntity.load("my_space:Thing")], instance_source=URIRef("my_source")
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        Concept(concept=cls_, implements=[ConceptEntity.load("my_space:Vehicle")], instance_source=URIRef("my_source")),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        Concept(
            concept=cls_,
            implements=[ConceptEntity.load("my_space:Vehicle"), ConceptEntity.load("my_space:Thing")],
            instance_source=URIRef("my_source"),
        ),
        id="Merge with combined",
    )


class TestMergeConceptual:
    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_model_test_cases()))
    def test_merge_models(
        self,
        primary: UnverifiedConceptualDataModel,
        secondary: UnverifiedConceptualDataModel,
        args: dict[str, object],
        expected: UnverifiedConceptualDataModel,
    ):
        primary_model = primary.as_verified_data_model()
        secondary_model = secondary.as_verified_data_model()
        expected_model = expected.as_verified_data_model()

        transformer = UnionConceptualDataModel(secondary_model, **args)
        merged = transformer.transform(primary_model)

        exclude = {"metadata": {"created", "updated"}}
        assert merged.dump(exclude=exclude) == expected_model.dump(exclude=exclude)

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_properties_test_cases()))
    def test_merge_properties(
        self,
        primary: ConceptualProperty,
        secondary: ConceptualProperty,
        args: dict[str, object],
        expected: ConceptualProperty,
    ) -> None:
        actual = UnionConceptualDataModel.union_properties(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_classes_test_cases()))
    def test_merge_classes(
        self,
        primary: Concept,
        secondary: Concept,
        args: dict[str, object],
        expected: Concept,
    ) -> None:
        actual = UnionConceptualDataModel.union_concepts(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize(
        "primary, secondary, expected",
        [
            pytest.param(
                dt.String(),
                dt.Integer(),
                MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
                id="String and Integer -> MultiValueTypeInfo",
            ),
            pytest.param(
                dt.Integer(),
                dt.Integer(),
                dt.Integer(),
                id="Integer and Integer -> Integer",
            ),
            pytest.param(
                ConceptEntity.load("my_space:Car"),
                ConceptEntity.load("my_space:Car"),
                ConceptEntity.load("my_space:Car"),
                id="Same ConceptEntity -> ConceptEntity",
            ),
            pytest.param(
                ConceptEntity.load("my_space:Car"),
                ConceptEntity.load("my_space:Vehicle"),
                MultiValueTypeInfo(types=[ConceptEntity.load("my_space:Car"), ConceptEntity.load("my_space:Vehicle")]),
                id="Different ConceptEntities -> MultiValueTypeInfo",
            ),
            pytest.param(
                MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
                dt.Boolean(),
                MultiValueTypeInfo(types=[dt.String(), dt.Integer(), dt.Boolean()]),
                id="MultiValueTypeInfo and new DataType -> MultiValueTypeInfo",
            ),
            pytest.param(
                MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
                dt.String(),
                MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
                id="MultiValueTypeInfo and existing DataType -> MultiValueTypeInfo (no dup)",
            ),
            pytest.param(
                MultiValueTypeInfo(types=[dt.String(), dt.Integer()]),
                MultiValueTypeInfo(types=[dt.Integer(), dt.Boolean()]),
                MultiValueTypeInfo(types=[dt.String(), dt.Integer(), dt.Boolean()]),
                id="MultiValueTypeInfo and MultiValueTypeInfo (overlap) -> MultiValueTypeInfo",
            ),
            pytest.param(
                UnknownEntity(),
                dt.String(),
                UnknownEntity(),
                id="UnknownEntity and DataType -> UnknownEntity",
            ),
            pytest.param(
                dt.String(),
                UnknownEntity(),
                UnknownEntity(),
                id="DataType and UnknownEntity -> UnknownEntity",
            ),
        ],
    )
    def test_merge_value_type(
        self,
        primary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
        secondary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
        expected: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
    ) -> None:
        actual = UnionConceptualDataModel.union_value_type(primary, secondary)

        assert actual.model_dump() == expected.model_dump()

    def test_merge_two_concepts_and_properties_from_different_models(self):
        car_concept = UnverifiedConcept("Car")
        car_property = UnverifiedConceptualProperty(
            "Car", "brand", "text", name="Brand", description="The brand of the car", min_count=1, max_count=1
        )
        model1 = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino"),
            concepts=SheetList([car_concept]),
            properties=SheetList([car_property]),
        ).as_verified_data_model()

        vehicle = UnverifiedConcept("Vehicle")
        car_concept2 = UnverifiedConcept("Car", implements="Vehicle")
        car_property2 = UnverifiedConceptualProperty("Car", "wheel_count", "integer")
        car_property3 = UnverifiedConceptualProperty("Car", "brand", "integer", min_count=0, max_count=1)
        model2 = UnverifiedConceptualDataModel(
            metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino"),
            concepts=SheetList([car_concept2, vehicle]),
            properties=SheetList([car_property2, car_property3]),
        ).as_verified_data_model()

        # Merge with combined join
        transformer = UnionConceptualDataModel(
            model2, join="combined", priority="secondary", conflict_resolution="combined"
        )
        merged = transformer.transform(model1)

        # Should contain both concepts and both properties
        merged_concepts = {c.concept.suffix for c in merged.concepts}
        property_names = {(p.concept.suffix, p.property_): p for p in merged.properties}
        assert merged_concepts == {"Car", "Vehicle"}
        assert set(property_names) == {("Car", "brand"), ("Car", "wheel_count")}
        brand = property_names[("Car", "brand")]
        assert brand.name == "Brand"
        assert brand.description == "The brand of the car"
