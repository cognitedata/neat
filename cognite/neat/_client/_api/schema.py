from collections.abc import Sequence
from typing import TYPE_CHECKING

from cognite.client import data_modeling as dm

from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, SpaceApplyDict, ViewApplyDict
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
        include_connections: bool = True,
        data_model_id: dm.DataModelId | None = None,
    ) -> DMSSchema:
        data_model_id = data_model_id or dm.DataModelId("NEAT_LOOKUP", "NEAT_LOOKUP", "NEAT_LOOKUP")
        if data_model_id.version is None:
            raise NeatValueError("Data model version must be specified")
        read_views = self._client.loaders.views.retrieve(
            list(view_ids),
            format="read",
            include_connected=include_connections,
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

    def retrieve_data_model_id(self, data_model_id: dm.DataModelIdentifier) -> DMSSchema:
        data_models = self._client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise NeatValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()
        return self.retrieve_data_model(data_model)

    def retrieve_data_model(
        self,
        data_model: dm.DataModel[dm.View],
    ) -> DMSSchema:
        """Create a schema from a data model.

        If a reference model is provided, the schema will include a reference schema. To determine which views,
        and containers to put in the reference schema, the following rule is applied:

            If a view or container space is different from the data model space,
            it will be included in the reference schema.*

        *One exception to this rule is if a view is directly referenced by the data model. In this case, the view will
        be included in the data model schema, even if the space is different.

        Args:
            data_model: The data model to create the schema from.

        Returns:
            DMSSchema: The schema created from the data model.
        """
        data_model_views = dm.ViewList(data_model.views)
        data_model_write = data_model.as_write()
        data_model_write.views = list(data_model_views.as_ids())

        container_ids = data_model_views.referenced_containers()
        containers = self._client.loaders.containers.retrieve(list(container_ids), include_connected=True)

        space_ids = [data_model.space]
        space_read = self._client.loaders.spaces.retrieve(space_ids)
        if len(space_read) != len(space_ids):
            raise NeatValueError(f"Space(s) {space_read} not found")
        space_write = space_read.as_write()

        existing_view_ids = set(data_model_views.as_ids())
        views_with_referenced = self._client.loaders.views.retrieve(
            list(existing_view_ids), include_connected=True, include_ancestor=True
        )

        # Converting views from read to write format requires to account for parents (implements)
        # as the read format contains all properties from all parents, while the write formate should not contain
        # properties from any parents.
        # The ViewLoader as_write method looks up parents and remove properties from them.
        view_write = ViewApplyDict([self._client.loaders.views.as_write(view) for view in views_with_referenced])

        container_write = ContainerApplyDict(containers.as_write())
        user_space = data_model.space
        return DMSSchema(
            spaces=SpaceApplyDict([s for s in space_write if s.space == user_space]),
            data_model=data_model_write,
            views=view_write,
            containers=container_write,
        )
