from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.containers import BTreeIndex

from cognite.neat.v0.core._client._api.data_modeling_loaders import (
    ContainerLoader,
    DataModelLoader,
    ViewLoader,
)

_DEFAULT_ARGS = dict(is_global=False, created_time=1, last_updated_time=1, name=None, description=None)


class TestDataModelLoader:
    def test_merge_data_models(self) -> None:
        local = dm.DataModelApply(
            "my_space",
            "my_model",
            "v1",
            views=[
                dm.ViewId("my_space", "view1", "v1"),
            ],
        )
        remote = dm.DataModel[dm.ViewId](
            "my_space",
            "my_model",
            "v1",
            views=[
                dm.ViewId("my_space", "view2", "v1"),
            ],
            **_DEFAULT_ARGS,
        )

        merged = DataModelLoader.merge(local, remote)

        assert (
            merged.dump()
            == dm.DataModelApply(
                "my_space",
                "my_model",
                "v1",
                views=[
                    dm.ViewId("my_space", "view2", "v1"),
                    dm.ViewId("my_space", "view1", "v1"),
                ],
            ).dump()
        )


class TestViewLoader:
    def test_merge_views(self) -> None:
        local = dm.ViewApply(
            "my_space",
            "view1",
            "v1",
            properties={
                "prop1": dm.MappedPropertyApply(dm.ContainerId("my_space", "container"), "prop1"),
            },
        )
        remote = dm.View(
            "my_space",
            "view1",
            "v1",
            properties={
                "prop2": dm.MappedProperty(
                    dm.ContainerId("my_space", "container"), "prop2", dm.data_types.Text(), True, False, False
                ),
            },
            used_for="node",
            writable=True,
            filter=None,
            implements=[dm.ViewId("my_space", "view2", "v1")],
            **_DEFAULT_ARGS,
        )

        merged = ViewLoader.merge(local, remote)

        assert (
            merged.dump()
            == dm.ViewApply(
                "my_space",
                "view1",
                "v1",
                properties={
                    "prop2": dm.MappedPropertyApply(dm.ContainerId("my_space", "container"), "prop2"),
                    "prop1": dm.MappedPropertyApply(dm.ContainerId("my_space", "container"), "prop1"),
                },
                implements=[dm.ViewId("my_space", "view2", "v1")],
            ).dump()
        )


class TestContainerLoader:
    def test_merge_containers(self) -> None:
        local = dm.ContainerApply(
            "my_space",
            "container",
            {
                "prop1": dm.ContainerProperty(dm.data_types.Text()),
            },
            used_for="node",
            constraints={
                "requiresDescribable": dm.RequiresConstraint(dm.ContainerId("cdf_cdm", "CogniteDescribable")),
            },
            indexes={
                "index1": BTreeIndex(["prop1"], cursorable=True),
            },
        )
        remote = dm.Container(
            "my_space",
            "container",
            {
                "prop2": dm.ContainerProperty(dm.data_types.Text()),
            },
            used_for="node",
            constraints={
                "requiresDescribable": dm.RequiresConstraint(dm.ContainerId("cdf_cdm", "CogniteDescribable")),
            },
            indexes={
                "index2": BTreeIndex(["prop2"], cursorable=True),
            },
            **_DEFAULT_ARGS,
        )

        merged = ContainerLoader.merge(local, remote)

        assert (
            merged.dump()
            == dm.ContainerApply(
                "my_space",
                "container",
                {
                    "prop2": dm.ContainerProperty(dm.data_types.Text()),
                    "prop1": dm.ContainerProperty(dm.data_types.Text()),
                },
                used_for="node",
                constraints={
                    "requiresDescribable": dm.RequiresConstraint(dm.ContainerId("cdf_cdm", "CogniteDescribable")),
                },
                indexes={
                    "index1": BTreeIndex(["prop1"], cursorable=True),
                    "index2": BTreeIndex(["prop2"], cursorable=True),
                },
            ).dump()
        )
