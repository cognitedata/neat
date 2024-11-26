from collections.abc import Sequence
from typing import TYPE_CHECKING

from cognite.client import data_modeling as dm

from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, ViewApplyDict
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._issues.errors import NeatValueError

if TYPE_CHECKING:
    from cognite.neat._client._api_client import NeatClient


class SchemaAPI:
    def __init__(self, client: "NeatClient") -> None:
        self._client = client

    def retrieve(
        self,
        view_ids: Sequence[dm.ViewId],
        container_ids: Sequence[dm.ContainerId],
        include_ancestors: bool = True,
        include_connections=True,
        data_model_id: dm.DataModelId | None = None,
    ) -> DMSSchema:
        data_model_id = data_model_id or dm.DataModelId("NEAT_LOOKUP", "NEAT_LOOKUP", "NEAT_LOOKUP")
        if data_model_id.version is None:
            raise NeatValueError("Data model version must be specified")
        read_views = self._client.loaders.views.retrieve(
            view_ids,  # type: ignore[arg-type]
            include_connections=include_connections,
            include_ancestor=include_ancestors,
        )
        views = ViewApplyDict([self._client.loaders.views.as_write(view) for view in read_views])

        container_set = set(container_ids) | {
            container for view in read_views for container in view.referenced_containers()
        }
        containers = self._client.loaders.containers.retrieve(list(container_set))

        return DMSSchema(
            data_model=dm.DataModelApply(
                space=data_model_id.space,
                external_id=data_model_id.external_id,
                version=data_model_id.version,
                views=list(views.keys()),
            ),
            views=views,
            containers=ContainerApplyDict(containers.as_write()),
        )
