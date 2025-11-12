import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._client._api.data_modeling_loaders import MultiCogniteAPIError
from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from tests.v0.data import SchemaData


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


@pytest.fixture(scope="session")
def deployed_space_and_container_strongly_coupled_model(cognite_client: CogniteClient) -> DMSSchema:
    schema = DMSSchema.from_directory(SchemaData.Physical.strongly_connected_model_folder)

    if not cognite_client.data_modeling.spaces.retrieve(list(schema.spaces.keys())):
        created_space = cognite_client.data_modeling.spaces.apply(list(schema.spaces.values()))
        assert len(created_space) == len(schema.spaces)

    if len(cognite_client.data_modeling.containers.retrieve(list(schema.containers.keys()))) != len(schema.containers):
        created_containers = cognite_client.data_modeling.containers.apply(list(schema.containers.values()))
        assert len(created_containers) == len(schema.containers)

    return schema


@pytest.mark.skip(reason="Legacy tests which we no longer maintain")
class TestViewLoader:
    def test_force_update(self, neat_client: NeatClient, container_props: dm.Container, space: dm.Space) -> None:
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

        new_created = neat_client.loaders.views.update([modified], force=True)[0]

        assert new_created.as_id() == original.as_id(), "The view version should be the same"
        assert new_created.properties["count"].container_property_identifier == new_prop, (
            "The property should have been updated"
        )

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

        assert len(cached_views) == len(views), "The cached views should be the same as the original views"

    def test_deploy_strongly_coupled(
        self, neat_client: NeatClient, deployed_space_and_container_strongly_coupled_model: DMSSchema
    ) -> None:
        schema = deployed_space_and_container_strongly_coupled_model
        try:
            created = neat_client.loaders.views.create(list(schema.views.values()))

            assert len(created) == len(schema.views)
        finally:
            neat_client.data_modeling.views.delete(list(schema.views.keys()))


@pytest.mark.skip(reason="Legacy tests which we no longer maintain")
class TestContainerLoader:
    def test_force_update(self, neat_client: NeatClient, space: dm.Space) -> None:
        original = dm.ContainerApply(
            space=space.space,
            external_id="test_container",
            properties={
                "name": dm.ContainerProperty(type=dm.Text()),
                "number": dm.ContainerProperty(type=dm.Int64(), nullable=True),
            },
            used_for="node",
        )
        retrieved = neat_client.data_modeling.containers.retrieve(original.as_id())
        if retrieved is None:
            neat_client.data_modeling.containers.apply(original)
            existing = original
        else:
            existing = retrieved

        node = dm.NodeApply(
            space=space.space,
            external_id="node_to_populate_container",
            sources=[
                dm.NodeOrEdgeData(
                    source=existing.as_id(),
                    properties={
                        "name": "Test",
                    },
                )
            ],
        )
        neat_client.data_modeling.instances.apply(node)

        modified = dm.ContainerApply.load(original.dump_yaml())
        # Change the type for each time the test runs to require a force update
        new_prop = dm.Float64() if isinstance(existing.properties["number"].type, dm.Int64) else dm.Int64()
        modified.properties["number"] = dm.ContainerProperty(type=new_prop)

        try:
            _ = neat_client.loaders.containers.update([modified], force=True, drop_data=False)[0]
        except CogniteAPIError as e:
            assert len(e.failed) == 1, "We should not have been able to update the container"
        else:
            raise AssertionError("We should not have been able to update the container")

        new_created = neat_client.loaders.containers.update([modified], force=True, drop_data=True)[0]
        assert new_created.as_id() == original.as_id(), "The container should be the same"
        assert new_created.properties["number"].type == new_prop, "The property should have been updated"

    def test_fallback_one_by_one(self, neat_client: NeatClient, space: dm.Space) -> None:
        valid_container = dm.ContainerApply(
            space=space.space,
            external_id="valid_container",
            properties={
                "name": dm.ContainerProperty(type=dm.Text()),
            },
        )
        invalid_container = dm.ContainerApply(
            space=space.space,
            external_id="invalid_container-$)()&",
            properties={
                "name": dm.ContainerProperty(type=dm.Text()),
            },
        )

        try:
            try:
                neat_client.loaders.containers.create([valid_container, invalid_container])
            except MultiCogniteAPIError as e:
                assert len(e.success) == 1, "Only one container should be created"
                assert len(e.failed) == 1, "Only one container should fail"
        finally:
            neat_client.data_modeling.containers.delete([valid_container.as_id()])


@pytest.mark.skip(reason="Legacy tests which we no longer maintain")
class TestSchemaLoader:
    def test_retrieve_schema(self, neat_client: NeatClient, space: dm.Space) -> None:
        schema = neat_client.schema.retrieve(
            [
                dm.ViewId("cdf_cdm", "CogniteAsset", "v1"),
                dm.ViewId("cdf_cdm", "CogniteDescribable", "v1"),
                dm.ViewId("cdf_cdm", "CogniteSourcable", "v1"),
                dm.ViewId("cdf_cdm", "CogniteFile", "v1"),
                dm.ViewId("cdf_cdm", "CogniteTimeSeries", "v1"),
            ],
            [
                dm.ContainerId("cdf_cdm", "CogniteFile"),
                dm.ContainerId("cdf_cdm", "CogniteTimeSeries"),
                dm.ContainerId("cdf_cdm", "CogniteDescribable"),
            ],
        )

        assert len(schema.containers) == 27
        assert len(schema.views) == 30
