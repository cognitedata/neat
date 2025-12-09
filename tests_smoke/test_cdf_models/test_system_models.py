import pytest
import yaml

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer._differ_view import ViewDiffer
from cognite.neat._data_model.deployer.data_classes import FieldChange, FieldChanges, PrimitiveField
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    ViewReference,
    ViewRequest,
    ViewResponse,
)
from tests_smoke.test_cdf_models.constants import (
    COGNITE_CORE_CONTAINER_YAML,
    COGNITE_CORE_ID,
    COGNITE_CORE_MODEL_YAML,
    COGNITE_CORE_VIEW_YAML,
    ENCODING,
)


@pytest.fixture(scope="session")
def cdf_cognite_core_model(neat_client: NeatClient) -> DataModelRequest:
    model = neat_client.data_models.retrieve([COGNITE_CORE_ID])
    assert len(model) == 1, "Expected to retrieve exactly one CogniteCore data model"
    return model[0].as_request()


@pytest.fixture(scope="session")
def cdf_cognite_core_views(
    neat_client: NeatClient, cdf_cognite_core_model: DataModelRequest
) -> dict[ViewReference, ViewResponse]:
    assert cdf_cognite_core_model.views, "CogniteCore model has no views"
    views = neat_client.views.retrieve(cdf_cognite_core_model.views, include_inherited_properties=True)
    return {view.as_reference(): view for view in views}


@pytest.fixture(scope="session")
def cdf_cognite_core_view_requests(
    cdf_cognite_core_views: dict[ViewReference, ViewResponse],
) -> dict[ViewReference, ViewRequest]:
    return {view_id: view.as_request() for view_id, view in cdf_cognite_core_views.items()}


@pytest.fixture(scope="session")
def cdf_cognite_core_containers(
    neat_client: NeatClient, cdf_cognite_core_views: dict[ViewReference, ViewResponse]
) -> dict[ContainerReference, ContainerRequest]:
    container_refs = {
        container_ref for view in cdf_cognite_core_views.values() for container_ref in view.mapped_containers
    }
    containers = neat_client.containers.retrieve(list(container_refs))
    return {container.as_reference(): container.as_request() for container in containers}


def local_views() -> list[ViewRequest]:
    return [
        ViewRequest.model_validate(item) for item in yaml.safe_load(COGNITE_CORE_VIEW_YAML.read_text(encoding=ENCODING))
    ]


def local_containers() -> list[ContainerRequest]:
    return [
        ContainerRequest.model_validate(item)
        for item in yaml.safe_load(COGNITE_CORE_CONTAINER_YAML.read_text(encoding=ENCODING))
    ]


@pytest.fixture()
def local_container_map() -> dict[ContainerReference, ContainerRequest]:
    return {container.as_reference(): container for container in local_containers()}


class TestCogniteCoreModel:
    def test_model_is_unchanged(self, cdf_cognite_core_model: DataModelRequest) -> None:
        local_model = DataModelRequest.model_validate(
            yaml.safe_load(COGNITE_CORE_MODEL_YAML.read_text(encoding=ENCODING))
        )

        changes = DataModelDiffer().diff(local_model, cdf_cognite_core_model)
        if changes:
            raise AssertionError(f"Cognite Core data model has changed:\n {humanize_changes(changes)}")

    @pytest.mark.parametrize("local_view", [pytest.param(view, id=str(view.as_reference())) for view in local_views()])
    def test_views_are_unchanged(
        self,
        local_view: ViewRequest,
        local_container_map: dict[ContainerReference, ContainerRequest],
        cdf_cognite_core_view_requests: dict[ViewReference, ViewRequest],
        cdf_cognite_core_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        current_view = cdf_cognite_core_view_requests.get(local_view.as_reference())
        assert current_view is not None, f"View {local_view.as_reference()} not found in current Cognite Core model"

        changes = ViewDiffer(local_container_map, cdf_cognite_core_containers).diff(local_view, current_view)
        if changes:
            raise AssertionError(f"View {local_view.as_reference()!s} has changed:\n {humanize_changes(changes)}")

    @pytest.mark.parametrize(
        "local_container",
        [pytest.param(container, id=str(container.as_reference())) for container in local_containers()],
    )
    def test_containers_are_unchanged(
        self,
        local_container: ContainerRequest,
        cdf_cognite_core_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        current_container = cdf_cognite_core_containers.get(local_container.as_reference())
        assert current_container is not None, (
            f"Container {local_container.as_reference()} not found in current Cognite Core model"
        )
        changes = ContainerDiffer().diff(local_container, current_container)
        if changes:
            raise AssertionError(
                f"Container {local_container.as_reference()!s} has changed:\n {humanize_changes(changes)}"
            )


def humanize_changes(changes: list[FieldChange]) -> str:
    primitive_changes = get_primitive_changes(changes)
    lines = []
    for change in primitive_changes:
        lines.append(f"- Field '{change.field_path}': {change.description}")
    return "\n".join(lines)


def get_primitive_changes(changes: list[FieldChange]) -> list[PrimitiveField]:
    primitive_changes: list[PrimitiveField] = []
    for change in changes:
        if isinstance(change, FieldChanges):
            primitive_changes.extend(get_primitive_changes(change.changes))
        elif isinstance(change, PrimitiveField):
            primitive_changes.append(change)
        else:
            raise RuntimeError(f"Unknown FieldChange type: {type(change)}")
    return primitive_changes
