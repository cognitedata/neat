import yaml

from cognite.neat import get_cognite_client
from cognite.neat._client import NeatClient
from tests_smoke.test_cdf_models.constants import (
    COGNITE_CORE_CONTAINER_YAML,
    COGNITE_CORE_ID,
    COGNITE_CORE_MODEL_YAML,
    COGNITE_CORE_VIEW_YAML,
    ENCODING,
)


def update_cognite_core_locally() -> None:
    client = NeatClient(get_cognite_client(".env"))
    print("Updating Cognite Core data model locally...")
    COGNITE_CORE_MODEL_YAML.parent.mkdir(parents=True, exist_ok=True)
    models = client.data_models.retrieve([COGNITE_CORE_ID])
    assert len(models) == 1
    cognite_core = models[0]
    COGNITE_CORE_MODEL_YAML.write_text(
        yaml.safe_dump(
            cognite_core.as_request().model_dump(mode="json", by_alias=True, exclude_unset=True), sort_keys=False
        ),
        encoding=ENCODING,
    )
    print(f"Written Cognite Core data model to {COGNITE_CORE_MODEL_YAML.as_posix()!r}")

    assert cognite_core.views is not None
    views = client.views.retrieve(cognite_core.views)
    COGNITE_CORE_VIEW_YAML.write_text(
        yaml.safe_dump(
            [view.as_request().model_dump(mode="json", by_alias=True, exclude_unset=True) for view in views]
        ),
        encoding=ENCODING,
    )
    print(f"Written Cognite Core views to {COGNITE_CORE_VIEW_YAML.as_posix()!r}")

    containers = {container_ref for view in views for container_ref in view.mapped_containers}
    containers_list = client.containers.retrieve(sorted(containers, key=str))  # Sort for consistent output
    COGNITE_CORE_CONTAINER_YAML.write_text(
        yaml.safe_dump(
            [
                container.as_request().model_dump(mode="json", by_alias=True, exclude_unset=True)
                for container in containers_list
            ]
        ),
        encoding=ENCODING,
    )
    print(f"Written Cognite Core containers to {COGNITE_CORE_CONTAINER_YAML.as_posix()!r}")


if __name__ == "__main__":
    update_cognite_core_locally()
