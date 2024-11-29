import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat._client import NeatClient


@pytest.fixture(scope="session")
def space(cognite_client: CogniteClient) -> dm.Space:
    space = dm.SpaceApply(
        space="test_space", description="This space is used by Neat for integration tests", name="Test Space"
    )
    return cognite_client.data_modeling.spaces.apply(space)


@pytest.fixture(scope="session")
def container_props(cognite_client: CogniteClient, space: dm.Space) -> dm.Container:
    container = dm.ContainerApply(
        space=space.space,
        external_id="PropContainer",
        properties={
            "name": dm.ContainerProperty(type=dm.Text()),
            "other": dm.ContainerProperty(type=dm.DirectRelation()),
            "number": dm.ContainerProperty(type=dm.Int64()),
            "float": dm.ContainerProperty(type=dm.Float64()),
        },
    )
    return cognite_client.data_modeling.containers.apply(container)


class TestViewLoader:
    def test_force_create(self, neat_client: NeatClient, container_props: dm.Container, space: dm.Space) -> None:
        container_id = container_props.as_id()
        original = dm.ViewApply(
            space=space.space,
            external_id="test_view",
            version="1",
            properties={
                "name": dm.MappedPropertyApply(container=container_id, container_property_identifier="name"),
                "other": dm.MappedPropertyApply(
                    container=container_id,
                    container_property_identifier="other",
                    source=dm.ViewId(space.space, "test_view", "1"),
                ),
                "count": dm.MappedPropertyApply(container=container_id, container_property_identifier="number"),
            },
        )
        retrieved_list = neat_client.data_modeling.views.retrieve(original.as_id())
        if not retrieved_list:
            neat_client.data_modeling.views.apply(original)
            existing = original
        else:
            existing = retrieved_list[0]
        modified = dm.ViewApply.load(original.dump_yaml())
        # Change the type for each time the test runs to require a force update
        new_prop = "float" if existing.properties["count"].container_property_identifier == "number" else "number"
        modified.properties["count"] = dm.MappedPropertyApply(
            container=container_id, container_property_identifier=new_prop
        )

        new_created = neat_client.loaders.views.create([modified], existing_handling="force")[0]

        assert new_created.as_id() == original.as_id(), "The view version should be the same"
        assert (
            new_created.properties["count"].container_property_identifier == new_prop
        ), "The property should have been updated"

    def test_find_all_connected(self, neat_client: NeatClient) -> None:
        views = neat_client.loaders.views.retrieve(
            [dm.ViewId("cdf_cdm", "CogniteAsset", "v1")], include_connected=True, include_ancestor=True
        )

        assert len(views) == 30, "This should return almost the entire CogniteCore model"

    def test_avoid_duplicates(self, neat_client: NeatClient) -> None:
        views = neat_client.loaders.views.retrieve(
            [dm.ViewId("cdf_cdm", "CogniteAsset", "v1"), dm.ViewId("cdf_cdm", "CogniteEquipment", "v1")],
            include_ancestor=True,
        )
        unique_views = set(views.as_ids())
        assert len(unique_views) == len(views), "There should be no duplicates in the list of views"

        cached_views = neat_client.loaders.views.retrieve(
            [dm.ViewId("cdf_cdm", "CogniteAsset", "v1"), dm.ViewId("cdf_cdm", "CogniteEquipment", "v1")],
            include_ancestor=True,
        )

        assert len(cached_views.as_ids()) == len(
            views.as_ids()
        ), "The cached views should be the same as the original views"


class TestContainerLoader:
    def test_force_create(self, neat_client: NeatClient, space: dm.Space) -> None:
        original = dm.ContainerApply(
            space=space.space,
            external_id="test_container",
            properties={
                "name": dm.ContainerProperty(type=dm.Text()),
                "number": dm.ContainerProperty(type=dm.Int64()),
            },
        )
        retrieved = neat_client.data_modeling.containers.retrieve(original.as_id())
        if retrieved is None:
            neat_client.data_modeling.containers.apply(original)
            existing = original
        else:
            existing = retrieved
        modified = dm.ContainerApply.load(original.dump_yaml())
        # Change the type for each time the test runs to require a force update
        new_prop = dm.Float64() if isinstance(existing.properties["number"].type, dm.Int64) else dm.Int64()
        modified.properties["number"] = dm.ContainerProperty(type=new_prop)

        new_created = neat_client.loaders.containers.create([modified], existing_handling="force")[0]

        assert new_created.as_id() == original.as_id(), "The container version should be the same"
        assert new_created.properties["number"].type == new_prop, "The property should have been updated"
