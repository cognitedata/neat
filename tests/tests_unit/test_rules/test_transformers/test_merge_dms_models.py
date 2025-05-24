from collections.abc import Iterable

import pytest

from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.entities import ConceptEntity, ContainerEntity, DMSNodeEntity, ViewEntity
from cognite.neat.core._data_model.models.physical import (
    PhysicalContainer,
    PhysicalEnum,
    PhysicalNodeType,
    PhysicalProperty,
    PhysicalView,
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalDataModel,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.core._data_model.transformers import MergePhysicalDataModel


def merge_model_test_cases() -> Iterable:
    metadata = UnverifiedPhysicalMetadata("my_space", "my_model", "doctrino", "v1")

    single_cls1 = UnverifiedPhysicalDataModel(
        metadata=metadata,
        views=[UnverifiedPhysicalView("PrimaryView")],
        properties=[
            UnverifiedPhysicalProperty(
                "PrimaryView",
                "primary_property",
                "text",
                container="PrimaryContainer",
                container_property="primary_property",
            )
        ],
        containers=[UnverifiedPhysicalContainer("PrimaryContainer")],
    )
    single_cls2 = UnverifiedPhysicalDataModel(
        metadata=metadata,
        views=[UnverifiedPhysicalView("SecondaryView")],
        properties=[
            UnverifiedPhysicalProperty(
                "SecondaryView",
                "secondary_property",
                "text",
                container="SecondaryContainer",
                container_property="secondary_property",
            )
        ],
        containers=[UnverifiedPhysicalContainer("SecondaryContainer")],
    )
    combined = UnverifiedPhysicalDataModel(
        metadata=metadata,
        views=[UnverifiedPhysicalView("PrimaryView"), UnverifiedPhysicalView("SecondaryView")],
        properties=[
            UnverifiedPhysicalProperty(
                "PrimaryView",
                "primary_property",
                "text",
                container="PrimaryContainer",
                container_property="primary_property",
            ),
            UnverifiedPhysicalProperty(
                "SecondaryView",
                "secondary_property",
                "text",
                container="SecondaryContainer",
                container_property="secondary_property",
            ),
        ],
        containers=[UnverifiedPhysicalContainer("PrimaryContainer"), UnverifiedPhysicalContainer("SecondaryContainer")],
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
    view = ViewEntity.load("my_space:Car(version=v1)")
    container1 = ContainerEntity.load("my_space:CarContainer")
    container2 = ContainerEntity.load("my_space:CarContainer2")
    first = PhysicalProperty(
        view=view,
        view_property="my_property",
        value_type=dt.String(),
        min_count=0,
        max_count=1,
        container=container1,
        container_property="my_property",
    )
    second = PhysicalProperty(
        view=view,
        view_property="my_property",
        value_type=dt.Integer(),
        name="My Property",
        min_count=0,
        max_count=5,
        container=container2,
        container_property="other_property",
    )
    yield pytest.param(
        first,
        second,
        PhysicalProperty(
            view=view,
            view_property="my_property",
            value_type=dt.String(),
            name="My Property",
            min_count=0,
            max_count=1,
            container=container1,
            container_property="my_property",
        ),
        id="Merge two properties.",
    )


def merge_views_test_cases() -> Iterable:
    view = ViewEntity.load("my_space:Car(version=v1)")
    first = PhysicalView(view=view, implements=[ViewEntity.load("my_space:Vehicle(version=v1)")])
    second = PhysicalView(view=view, implements=[ViewEntity.load("my_space:Thing(version=v1)")], name="Car")
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        PhysicalView(view=view, implements=[ViewEntity.load("my_space:Vehicle(version=v1)")], name="Car"),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        PhysicalView(
            view=view,
            name="Car",
            implements=[ViewEntity.load("my_space:Vehicle(version=v1)"), ViewEntity.load("my_space:Thing(version=v1)")],
        ),
        id="Merge with combined",
    )


def merge_containers_test_cases() -> Iterable:
    container = ContainerEntity.load("my_space:CarContainer")
    first = PhysicalContainer(container=container, used_for="node")
    second = PhysicalContainer(
        container=container,
        name="Car Container",
        description="This is a car container",
        used_for="all",
    )
    yield pytest.param(
        first,
        second,
        PhysicalContainer(
            container=container,
            name="Car Container",
            description="This is a car container",
            used_for="node",
        ),
        id="Merge two containers.",
    )


def merge_node_test_cases() -> Iterable:
    node = DMSNodeEntity.load("my_space:CarNode")
    primary = PhysicalNodeType(node=node, usage="type")
    secondary = PhysicalNodeType(
        node=node,
        name="Car Node",
        description="This is a car node",
        usage="type",
    )
    yield pytest.param(
        primary,
        secondary,
        PhysicalNodeType(
            node=node,
            name="Car Node",
            description="This is a car node",
            usage="type",
        ),
        id="Merge two nodes.",
    )


def merge_enum_test_cases() -> Iterable:
    collection = ConceptEntity.load("my_space:MyCollection")
    primary = PhysicalEnum(
        collection=collection,
        value="my_value",
    )
    secondary = PhysicalEnum(
        collection=collection,
        value="my_value",
        name="My Value",
        description="This is my value",
    )
    yield pytest.param(
        primary,
        secondary,
        PhysicalEnum(
            collection=collection,
            name="My Value",
            description="This is my value",
            value="my_value",
        ),
        id="Merge two enums.",
    )


class TestMergeConceptual:
    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_model_test_cases()))
    def test_merge_models(
        self,
        primary: UnverifiedPhysicalDataModel,
        secondary: UnverifiedPhysicalDataModel,
        args: dict[str, object],
        expected: UnverifiedPhysicalDataModel,
    ):
        primary_model = primary.as_verified_data_model()
        secondary_model = secondary.as_verified_data_model()
        expected_model = expected.as_verified_data_model()

        transformer = MergePhysicalDataModel(secondary_model, **args)
        merged = transformer.transform(primary_model)

        exclude = {"metadata": {"created", "updated"}}
        assert merged.dump(exclude=exclude) == expected_model.dump(exclude=exclude)

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_properties_test_cases()))
    def test_merge_properties(
        self,
        primary: PhysicalProperty,
        secondary: PhysicalProperty,
        expected: PhysicalProperty,
    ) -> None:
        actual = MergePhysicalDataModel.merge_properties(primary, secondary)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_views_test_cases()))
    def test_merge_views(
        self,
        primary: PhysicalView,
        secondary: PhysicalView,
        args: dict[str, object],
        expected: PhysicalView,
    ) -> None:
        actual = MergePhysicalDataModel.merge_views(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_containers_test_cases()))
    def test_merge_containers(
        self,
        primary: PhysicalContainer,
        secondary: PhysicalContainer,
        expected: PhysicalContainer,
    ) -> None:
        actual = MergePhysicalDataModel.merge_containers(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_node_test_cases()))
    def test_merge_nodes(
        self,
        primary: PhysicalNodeType,
        secondary: PhysicalNodeType,
        expected: PhysicalNodeType,
    ) -> None:
        actual = MergePhysicalDataModel.merge_nodes(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_enum_test_cases()))
    def test_merge_enums(
        self,
        primary: PhysicalEnum,
        secondary: PhysicalEnum,
        expected: PhysicalEnum,
    ) -> None:
        actual = MergePhysicalDataModel.merge_enum(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    def test_merge_models_duplicated_properties(self) -> None:
        existing = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                UnverifiedPhysicalProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                UnverifiedPhysicalProperty(
                    "Equipment",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                UnverifiedPhysicalProperty(
                    "Equipment",
                    "asset",
                    "Asset",
                    connection="direct",
                    min_count=0,
                    max_count=1,
                    container="Equipment",
                    container_property="asset",
                ),
            ],
            views=[UnverifiedPhysicalView("Asset"), UnverifiedPhysicalView("Equipment")],
            containers=[
                UnverifiedPhysicalContainer("CogniteDescribable"),
                UnverifiedPhysicalContainer("CogniteEquipment"),
            ],
        ).as_verified_data_model()
        additional = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                UnverifiedPhysicalProperty(
                    "MyAsset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="MyAssetContainer",
                    container_property="name",
                ),
                UnverifiedPhysicalProperty(
                    "MyAsset",
                    "tags",
                    "text",
                    min_count=0,
                    max_count=1000,
                    container="MyAssetContainer",
                    container_property="tags",
                ),
                UnverifiedPhysicalProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="description",
                ),
            ],
            views=[UnverifiedPhysicalView("MyAsset"), UnverifiedPhysicalView("Asset")],
            containers=[
                UnverifiedPhysicalContainer("MyAssetContainer"),
                UnverifiedPhysicalContainer("CogniteDescribable"),
            ],
        ).as_verified_data_model()

        actual = MergePhysicalDataModel(additional).transform(existing)

        assert len(actual.containers) == 3
        assert {c.container.suffix for c in actual.containers} == {
            "CogniteDescribable",
            "CogniteEquipment",
            "MyAssetContainer",
        }
        assert len(actual.views) == 3
        assert {v.view.suffix for v in actual.views} == {"MyAsset", "Asset", "Equipment"}
        assert len(actual.properties) == 5
        assert {(p.view.suffix, p.view_property) for p in actual.properties} == {
            ("MyAsset", "name"),
            ("MyAsset", "tags"),
            ("Asset", "name"),
            ("Equipment", "name"),
            ("Equipment", "asset"),
        }
