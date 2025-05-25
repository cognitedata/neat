from collections.abc import Iterable

import pytest
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerId, ContainerProperty, Text
from cognite.client.data_classes.data_modeling.containers import (
    BTreeIndex,
    InvertedIndex,
    RequiresConstraint,
    UniquenessConstraint,
)

from cognite.neat.core._client._api.crud import ContainerCrudAPI
from cognite.neat.core._client.data_classes.deploy_result import Property, PropertyChange, ResourceDifference


def container_difference_merge_test_cases() -> Iterable:
    base = ContainerApply(
        space="my_space",
        external_id="container1",
        description="Old description",
        properties={"name": ContainerProperty(Text())},
        used_for="node",
        constraints={"uniqueName": UniquenessConstraint(properties=["name"])},
        indexes={"nameIndex": BTreeIndex(cursorable=True, properties=["name"])},
    )
    # Copy
    new1 = ContainerApply._load(base.dump())
    new1.description = "New description"
    new1.name = "New Name"
    yield pytest.param(
        new1,
        base,
        ResourceDifference(
            resource_id=base.as_id(),
            added=[Property(location="name", value_representation=new1.name)],
            removed=[],
            changed=[
                PropertyChange(
                    location="description",
                    value_representation=new1.description,
                    previous_representation=base.description,
                ),
            ],
        ),
        new1,
        id="Updated description and added name",
    )

    new2 = ContainerApply._load(base.dump())
    new2.properties["name"] = ContainerProperty(Text(), nullable=False)
    new2.properties["tags"] = ContainerProperty(Text(is_list=True))
    yield pytest.param(
        new2,
        base,
        ResourceDifference(
            resource_id=base.as_id(),
            added=[Property(location="properties.tags")],
            removed=[],
            changed=[PropertyChange("properties.name")],
        ),
        new2,
        id="Updated properties with non-nullable name and added tags",
    )

    new3 = ContainerApply._load(base.dump())
    new3.properties = {}
    new3.indexes = {}
    new3.constraints = {}
    new3.properties["tags"] = ContainerProperty(Text(is_list=True))
    new3.constraints["required"] = RequiresConstraint(ContainerId("my_space", "other_container"))
    new3.indexes["tagsIndex"] = InvertedIndex(properties=["tags"])
    merged = ContainerApply._load(new3.dump())
    merged.properties["name"] = base.properties["name"]
    merged.indexes["nameIndex"] = base.indexes["nameIndex"]
    merged.constraints["uniqueName"] = base.constraints["uniqueName"]

    yield pytest.param(
        new3,
        base,
        ResourceDifference(
            resource_id=base.as_id(),
            added=[
                Property(location="properties.tags"),
                Property(location="indexes.tagsIndex"),
                Property(location="constraints.required"),
            ],
        ),
        merged,
        id="Merge properties, indexes, and constraints with existing ones.",
    )


class TestContainerCrudAPI:
    @pytest.mark.parametrize("new, previous, difference, merged", list(container_difference_merge_test_cases()))
    def test_difference(
        self, new: ContainerApply, previous: ContainerApply, difference: ResourceDifference, merged: ContainerApply
    ) -> None:
        assert ContainerCrudAPI.difference(new, previous) == difference

    @pytest.mark.parametrize("new, previous, difference, merged", list(container_difference_merge_test_cases()))
    def test_merge(
        self, new: ContainerApply, previous: ContainerApply, difference: ResourceDifference, merged: ContainerApply
    ) -> None:
        assert ContainerCrudAPI.merge(new, previous) == merged
