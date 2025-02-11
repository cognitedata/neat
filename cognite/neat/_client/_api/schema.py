from collections import defaultdict
from collections.abc import Mapping, Sequence
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING

from cognite.client import data_modeling as dm

from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, SpaceApplyDict, ViewApplyDict
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._constants import is_readonly_property
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

    @staticmethod
    def order_views_by_container_dependencies(
        views_by_id: Mapping[dm.ViewId, dm.View | dm.ViewApply],
        containers: Sequence[dm.Container | dm.ContainerApply],
        skip_readonly: bool = False,
    ) -> tuple[list[dm.ViewId], dict[dm.ViewId, set[str]]]:
        """Sorts the views by container constraints."""
        container_by_id = {container.as_id(): container for container in containers}
        views_by_container = defaultdict(set)
        for view_id, view in views_by_id.items():
            for container_id in view.referenced_containers():
                views_by_container[container_id].add(view_id)

        properties_dependent_on_self: dict[dm.ViewId, set[str]] = defaultdict(set)
        view_id_by_dependencies: dict[dm.ViewId, set[dm.ViewId]] = {}
        for view_id, view in views_by_id.items():
            dependencies = set()
            for prop_id, prop in (view.properties or {}).items():
                if not isinstance(prop, dm.MappedProperty | dm.MappedPropertyApply):
                    continue
                if skip_readonly and is_readonly_property(prop.container, prop.container_property_identifier):
                    continue
                container = container_by_id[prop.container]
                container_prop = container.properties[prop.container_property_identifier]
                if not isinstance(container_prop.type, dm.DirectRelation):
                    continue
                if prop.source == view_id:
                    properties_dependent_on_self[view_id].add(prop_id)
                for constraint in container.constraints.values():
                    if isinstance(constraint, dm.RequiresConstraint):
                        view_dependencies = views_by_container.get(constraint.require, set())
                        if view_id in view_dependencies:
                            # Dependency on self
                            properties_dependent_on_self[view_id].add(prop_id)
                            view_dependencies.remove(view_id)
                        dependencies.update(view_dependencies)
            view_id_by_dependencies[view_id] = dependencies

        ordered_view_ids = list(TopologicalSorter(view_id_by_dependencies).static_order())

        return list(ordered_view_ids), properties_dependent_on_self
