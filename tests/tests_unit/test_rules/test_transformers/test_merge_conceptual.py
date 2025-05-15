from collections.abc import Iterable

import pytest
from rdflib import URIRef

from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.conceptual import (
    ConceptualClass,
    ConceptualProperty,
    UnverifiedConceptualClass,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.core._data_model.models.entities import ConceptEntity, MultiValueTypeInfo
from cognite.neat.core._data_model.transformers import MergeConceptualDataModel


def merge_model_test_cases() -> Iterable:
    metadata = UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino")

    single_cls1 = UnverifiedConceptualDataModel(
        metadata=metadata,
        classes=[UnverifiedConceptualClass("PrimaryClass")],
        properties=[UnverifiedConceptualProperty("PrimaryClass", "primary_property", "text")],
    )
    single_cls2 = UnverifiedConceptualDataModel(
        metadata=metadata,
        classes=[UnverifiedConceptualClass("SecondaryClass")],
        properties=[UnverifiedConceptualProperty("SecondaryClass", "secondary_property", "text")],
    )
    combined = UnverifiedConceptualDataModel(
        metadata=metadata,
        classes=[UnverifiedConceptualClass("PrimaryClass"), UnverifiedConceptualClass("SecondaryClass")],
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
    first = ConceptualProperty(class_=cls_, property_="my_property", value_type=dt.String(), min_count=0, max_count=1)
    second = ConceptualProperty(
        class_=cls_,
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
            class_=cls_,
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
            class_=cls_,
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
    first = ConceptualClass(class_=cls_, implements=[ConceptEntity.load("my_space:Vehicle")])
    second = ConceptualClass(
        class_=cls_, implements=[ConceptEntity.load("my_space:Thing")], instance_source=URIRef("my_source")
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        ConceptualClass(
            class_=cls_, implements=[ConceptEntity.load("my_space:Vehicle")], instance_source=URIRef("my_source")
        ),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        ConceptualClass(
            class_=cls_,
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
        primary_model = primary.as_verified_rules()
        secondary_model = secondary.as_verified_rules()
        expected_model = expected.as_verified_rules()

        transformer = MergeConceptualDataModel(secondary_model, **args)
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
        actual = MergeConceptualDataModel.merge_properties(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_classes_test_cases()))
    def test_merge_classes(
        self,
        primary: ConceptualClass,
        secondary: ConceptualClass,
        args: dict[str, object],
        expected: ConceptualClass,
    ) -> None:
        actual = MergeConceptualDataModel.merge_classes(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()
