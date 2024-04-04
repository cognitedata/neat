import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm


@pytest.fixture(scope="session")
def space(cognite_client: CogniteClient) -> dm.Space:
    space = dm.SpaceApply(space="test_space", description="This space is used by Neat for integration tests", name="Test Space")
    return cognite_client.data_modeling.spaces.create(space)


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
        }
    )
    return cognite_client.data_modeling.containers.create(container)


class TestViewLoader:
    def test_force_create(self, cognite_client: CogniteClient, container_props: dm.Container, space: dm.Space) -> None:
        container_id = container_props.as_id()
        view = dm.View(
            space=space.space,
            external_id="test_view",
            version="1",
            properties={
            },
        )
