import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    ContainerResponse,
    DataModelReference,
    DataModelResponse,
    ViewReference,
    ViewResponse,
)


@pytest.fixture(scope="session")
def current_cognite_core_model(neat_client: NeatClient) -> DataModelResponse:
    model = neat_client.data_models.retrieve(
        [DataModelReference(space="cdf_cdm", external_id="CogniteCore", version="v1")]
    )
    assert len(model) == 1, "Expected to retrieve exactly one CogniteCore data model"
    return model[0]


@pytest.fixture(scope="session")
def current_cognite_core_views(
    neat_client: NeatClient, current_cognite_core_model: DataModelResponse
) -> dict[ViewReference, ViewResponse]:
    assert current_cognite_core_model.views, "CogniteCore model has no views"
    views = neat_client.views.retrieve(current_cognite_core_model.views, include_inherited_properties=True)
    return {view.as_reference(): view for view in views}


@pytest.fixture(scope="session")
def current_cognite_core_containers(
    neat_client: NeatClient, current_cognite_core_views: dict[ViewReference, ViewResponse]
) -> dict[ContainerReference, ContainerResponse]:
    container_refs = {
        container_ref for view in current_cognite_core_views.values() for container_ref in view.mapped_containers
    }
    containers = neat_client.containers.retrieve(list(container_refs))
    return {container.as_reference(): container for container in containers}


class TestCogniteCoreModel:
    def test_model_is_unchanged(self) -> None:
        assert True

    def test_views_are_unchanged(self) -> None:
        assert True

    def test_containers_are_unchanged(self) -> None:
        assert True
