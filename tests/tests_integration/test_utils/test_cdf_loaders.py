import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat.utils.cdf.cdf_loaders import ContainerLoader, ViewLoader


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
    def test_force_create(self, cognite_client: CogniteClient, container_props: dm.Container, space: dm.Space) -> None:
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
        retrieved_list = cognite_client.data_modeling.views.retrieve(original.as_id())
        if not retrieved_list:
            cognite_client.data_modeling.views.apply(original)
            existing = original
        else:
            existing = retrieved_list[0]
        modified = dm.ViewApply.load(original.dump_yaml())
        # Change the type for each time the test runs to require a force update
        new_prop = "float" if existing.properties["count"].container_property_identifier == "number" else "number"
        modified.properties["count"] = dm.MappedPropertyApply(
            container=container_id, container_property_identifier=new_prop
        )

        loader = ViewLoader(cognite_client, existing_handling="force")
        new_created = loader.create([modified])[0]

        assert new_created.as_id() == original.as_id(), "The view version should be the same"
        assert (
            new_created.properties["count"].container_property_identifier == new_prop
        ), "The property should have been updated"


class TestContainerLoader:
    def test_force_create(self, cognite_client: CogniteClient, space: dm.Space) -> None:
        original = dm.ContainerApply(
            space=space.space,
            external_id="test_container",
            properties={
                "name": dm.ContainerProperty(type=dm.Text()),
                "number": dm.ContainerProperty(type=dm.Int64()),
            },
        )
        retrieved = cognite_client.data_modeling.containers.retrieve(original.as_id())
        if retrieved is None:
            cognite_client.data_modeling.containers.apply(original)
            existing = original
        else:
            existing = retrieved
        modified = dm.ContainerApply.load(original.dump_yaml())
        # Change the type for each time the test runs to require a force update
        new_prop = dm.Float64() if isinstance(existing.properties["number"].type, dm.Int64) else dm.Int64()
        modified.properties["number"] = dm.ContainerProperty(type=new_prop)

        loader = ContainerLoader(cognite_client, existing_handling="force")
        new_created = loader.create([modified])[0]

        assert new_created.as_id() == original.as_id(), "The container version should be the same"
        assert new_created.properties["number"].type == new_prop, "The property should have been updated"
