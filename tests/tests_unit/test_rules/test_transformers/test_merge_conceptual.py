from collections.abc import Iterable

import pytest
from rdflib import URIRef

from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.entities import ClassEntity, MultiValueTypeInfo
from cognite.neat.core._data_model.models.information import (
    InformationClass,
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
    InformationInputRules,
    InformationProperty,
)
from cognite.neat.core._data_model.transformers import MergeInformationRules


def merge_model_test_cases() -> Iterable:
    metadata = InformationInputMetadata("my_space", "my_model", "v1", "doctrino")

    single_cls1 = InformationInputRules(
        metadata=metadata,
        classes=[InformationInputClass("PrimaryClass")],
        properties=[InformationInputProperty("PrimaryClass", "primary_property", "text")],
    )
    single_cls2 = InformationInputRules(
        metadata=metadata,
        classes=[InformationInputClass("SecondaryClass")],
        properties=[InformationInputProperty("SecondaryClass", "secondary_property", "text")],
    )
    combined = InformationInputRules(
        metadata=metadata,
        classes=[InformationInputClass("PrimaryClass"), InformationInputClass("SecondaryClass")],
        properties=[
            InformationInputProperty("PrimaryClass", "primary_property", "text"),
            InformationInputProperty("SecondaryClass", "secondary_property", "text"),
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
    cls_ = ClassEntity.load("my_space:Car")
    first = InformationProperty(class_=cls_, property_="my_property", value_type=dt.String(), min_count=0, max_count=1)
    second = InformationProperty(
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
        InformationProperty(
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
        InformationProperty(
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
    cls_ = ClassEntity.load("my_space:Car")
    first = InformationClass(class_=cls_, implements=[ClassEntity.load("my_space:Vehicle")])
    second = InformationClass(
        class_=cls_, implements=[ClassEntity.load("my_space:Thing")], instance_source=URIRef("my_source")
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        InformationClass(
            class_=cls_, implements=[ClassEntity.load("my_space:Vehicle")], instance_source=URIRef("my_source")
        ),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        InformationClass(
            class_=cls_,
            implements=[ClassEntity.load("my_space:Vehicle"), ClassEntity.load("my_space:Thing")],
            instance_source=URIRef("my_source"),
        ),
        id="Merge with combined",
    )


class TestMergeConceptual:
    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_model_test_cases()))
    def test_merge_models(
        self,
        primary: InformationInputRules,
        secondary: InformationInputRules,
        args: dict[str, object],
        expected: InformationInputRules,
    ):
        primary_model = primary.as_verified_rules()
        secondary_model = secondary.as_verified_rules()
        expected_model = expected.as_verified_rules()

        transformer = MergeInformationRules(secondary_model, **args)
        merged = transformer.transform(primary_model)

        assert merged.dump() == expected_model.dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_properties_test_cases()))
    def test_merge_properties(
        self,
        primary: InformationProperty,
        secondary: InformationProperty,
        args: dict[str, object],
        expected: InformationProperty,
    ) -> None:
        actual = MergeInformationRules.merge_properties(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_classes_test_cases()))
    def test_merge_classes(
        self,
        primary: InformationClass,
        secondary: InformationClass,
        args: dict[str, object],
        expected: InformationClass,
    ) -> None:
        actual = MergeInformationRules.merge_classes(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()
