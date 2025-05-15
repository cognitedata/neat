from collections.abc import Iterable

import pytest

from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.dms import (
    DMSContainer,
    DMSEnum,
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
    DMSNode,
    DMSProperty,
    DMSView,
)
from cognite.neat.core._data_model.models.entities import ConceptEntity, ContainerEntity, DMSNodeEntity, ViewEntity
from cognite.neat.core._data_model.transformers import MergeDMSRules


def merge_model_test_cases() -> Iterable:
    metadata = DMSInputMetadata("my_space", "my_model", "doctrino", "v1")

    single_cls1 = DMSInputRules(
        metadata=metadata,
        views=[DMSInputView("PrimaryView")],
        properties=[
            DMSInputProperty(
                "PrimaryView",
                "primary_property",
                "text",
                container="PrimaryContainer",
                container_property="primary_property",
            )
        ],
        containers=[DMSInputContainer("PrimaryContainer")],
    )
    single_cls2 = DMSInputRules(
        metadata=metadata,
        views=[DMSInputView("SecondaryView")],
        properties=[
            DMSInputProperty(
                "SecondaryView",
                "secondary_property",
                "text",
                container="SecondaryContainer",
                container_property="secondary_property",
            )
        ],
        containers=[DMSInputContainer("SecondaryContainer")],
    )
    combined = DMSInputRules(
        metadata=metadata,
        views=[DMSInputView("PrimaryView"), DMSInputView("SecondaryView")],
        properties=[
            DMSInputProperty(
                "PrimaryView",
                "primary_property",
                "text",
                container="PrimaryContainer",
                container_property="primary_property",
            ),
            DMSInputProperty(
                "SecondaryView",
                "secondary_property",
                "text",
                container="SecondaryContainer",
                container_property="secondary_property",
            ),
        ],
        containers=[DMSInputContainer("PrimaryContainer"), DMSInputContainer("SecondaryContainer")],
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
    first = DMSProperty(
        view=view,
        view_property="my_property",
        value_type=dt.String(),
        min_count=0,
        max_count=1,
        container=container1,
        container_property="my_property",
    )
    second = DMSProperty(
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
        DMSProperty(
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
    first = DMSView(view=view, implements=[ViewEntity.load("my_space:Vehicle(version=v1)")])
    second = DMSView(view=view, implements=[ViewEntity.load("my_space:Thing(version=v1)")], name="Car")
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "priority"},
        DMSView(view=view, implements=[ViewEntity.load("my_space:Vehicle(version=v1)")], name="Car"),
        id="Merge with priority",
    )
    yield pytest.param(
        first,
        second,
        {"conflict_resolution": "combined"},
        DMSView(
            view=view,
            name="Car",
            implements=[ViewEntity.load("my_space:Vehicle(version=v1)"), ViewEntity.load("my_space:Thing(version=v1)")],
        ),
        id="Merge with combined",
    )


def merge_containers_test_cases() -> Iterable:
    container = ContainerEntity.load("my_space:CarContainer")
    first = DMSContainer(container=container, used_for="node")
    second = DMSContainer(
        container=container,
        name="Car Container",
        description="This is a car container",
        used_for="all",
    )
    yield pytest.param(
        first,
        second,
        DMSContainer(
            container=container,
            name="Car Container",
            description="This is a car container",
            used_for="node",
        ),
        id="Merge two containers.",
    )


def merge_node_test_cases() -> Iterable:
    node = DMSNodeEntity.load("my_space:CarNode")
    primary = DMSNode(node=node, usage="type")
    secondary = DMSNode(
        node=node,
        name="Car Node",
        description="This is a car node",
        usage="type",
    )
    yield pytest.param(
        primary,
        secondary,
        DMSNode(
            node=node,
            name="Car Node",
            description="This is a car node",
            usage="type",
        ),
        id="Merge two nodes.",
    )


def merge_enum_test_cases() -> Iterable:
    collection = ConceptEntity.load("my_space:MyCollection")
    primary = DMSEnum(
        collection=collection,
        value="my_value",
    )
    secondary = DMSEnum(
        collection=collection,
        value="my_value",
        name="My Value",
        description="This is my value",
    )
    yield pytest.param(
        primary,
        secondary,
        DMSEnum(
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
        primary: DMSInputRules,
        secondary: DMSInputRules,
        args: dict[str, object],
        expected: DMSInputRules,
    ):
        primary_model = primary.as_verified_rules()
        secondary_model = secondary.as_verified_rules()
        expected_model = expected.as_verified_rules()

        transformer = MergeDMSRules(secondary_model, **args)
        merged = transformer.transform(primary_model)

        exclude = {"metadata": {"created", "updated"}}
        assert merged.dump(exclude=exclude) == expected_model.dump(exclude=exclude)

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_properties_test_cases()))
    def test_merge_properties(
        self,
        primary: DMSProperty,
        secondary: DMSProperty,
        expected: DMSProperty,
    ) -> None:
        actual = MergeDMSRules.merge_properties(primary, secondary)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, args, expected", list(merge_views_test_cases()))
    def test_merge_views(
        self,
        primary: DMSView,
        secondary: DMSView,
        args: dict[str, object],
        expected: DMSView,
    ) -> None:
        actual = MergeDMSRules.merge_views(primary, secondary, **args)

        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_containers_test_cases()))
    def test_merge_containers(
        self,
        primary: DMSContainer,
        secondary: DMSContainer,
        expected: DMSContainer,
    ) -> None:
        actual = MergeDMSRules.merge_containers(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_node_test_cases()))
    def test_merge_nodes(
        self,
        primary: DMSNode,
        secondary: DMSNode,
        expected: DMSNode,
    ) -> None:
        actual = MergeDMSRules.merge_nodes(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("primary, secondary, expected", list(merge_enum_test_cases()))
    def test_merge_enums(
        self,
        primary: DMSEnum,
        secondary: DMSEnum,
        expected: DMSEnum,
    ) -> None:
        actual = MergeDMSRules.merge_enum(primary, secondary)
        assert actual.model_dump() == expected.model_dump()

    def test_merge_models_duplicated_properties(self) -> None:
        existing = DMSInputRules(
            metadata=DMSInputMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                DMSInputProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                DMSInputProperty(
                    "Equipment",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="name",
                ),
                DMSInputProperty(
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
            views=[DMSInputView("Asset"), DMSInputView("Equipment")],
            containers=[
                DMSInputContainer("CogniteDescribable"),
                DMSInputContainer("CogniteEquipment"),
            ],
        ).as_verified_rules()
        additional = DMSInputRules(
            metadata=DMSInputMetadata("my_model", "v1", "neat", "doctrino"),
            properties=[
                DMSInputProperty(
                    "MyAsset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="MyAssetContainer",
                    container_property="name",
                ),
                DMSInputProperty(
                    "MyAsset",
                    "tags",
                    "text",
                    min_count=0,
                    max_count=1000,
                    container="MyAssetContainer",
                    container_property="tags",
                ),
                DMSInputProperty(
                    "Asset",
                    "name",
                    "text",
                    min_count=0,
                    max_count=1,
                    container="CogniteDescribable",
                    container_property="description",
                ),
            ],
            views=[DMSInputView("MyAsset"), DMSInputView("Asset")],
            containers=[
                DMSInputContainer("MyAssetContainer"),
                DMSInputContainer("CogniteDescribable"),
            ],
        ).as_verified_rules()

        actual = MergeDMSRules(additional).transform(existing)

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
