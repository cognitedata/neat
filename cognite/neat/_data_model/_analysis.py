from graphlib import TopologicalSorter

from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    ReverseDirectRelationProperty,
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.models.dms._views import ViewRequest


class DataModelAnalysis:
    def __init__(
        self,
        physical: RequestSchema | None = None,
    ) -> None:
        self._physical = physical

    @property
    def physical(self) -> RequestSchema:
        if self._physical is None:
            raise ValueError("Physical Data Model is required for this analysis")
        return self._physical

    def referenced_views(self, include_connection_end_node_types: bool = False) -> set[ViewReference]:
        """Get all referenced views in the physical data model."""
        referenced_views = set()

        for view in self.physical.views:
            referenced_views.add(view.as_reference())
            if view.implements:
                for implement in view.implements:
                    referenced_views.add(implement)

        if include_connection_end_node_types:
            referenced_views |= set(self.connection_end_node_types.values())

        return referenced_views

    @property
    def referenced_containers(self) -> set[ContainerReference]:
        """Get all referenced containers in the physical data model."""
        referenced_containers = set()

        for view in self.physical.views:
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    referenced_containers.add(property_.container)

        for container in self.physical.containers:
            referenced_containers.add(container.as_reference())

        return referenced_containers

    @property
    def view_ancestors(self) -> dict[ViewReference, set[ViewReference]]:
        """Get a mapping of each view to its ancestors in the physical data model."""
        implements_by_view = self.implements_by_view

        # Topological sort to ensure that concepts include all ancestors
        for view in list(TopologicalSorter(implements_by_view).static_order()):
            if view not in implements_by_view:
                continue
            implements_by_view[view] |= {
                grand_parent
                for parent in implements_by_view[view]
                for grand_parent in implements_by_view.get(parent, set())
            }

        return implements_by_view

    @property
    def implements_by_view(self) -> dict[ViewReference, set[ViewReference]]:
        """Get a mapping of each view to the views it implements."""
        implements_mapping: dict[ViewReference, set[ViewReference]] = {}

        for view in self.physical.views:
            view_ref = view.as_reference()
            if view_ref not in implements_mapping:
                implements_mapping[view_ref] = set()
            if view.implements:
                for implement in view.implements:
                    implements_mapping[view_ref].add(implement)

        return implements_mapping

    def view_by_reference(self, include_inherited_properties: bool = True) -> dict[ViewReference, ViewRequest]:
        """Get a mapping of view references to their corresponding ViewRequest objects."""
        view_ancestors = self.view_ancestors

        view_by_reference: dict[ViewReference, ViewRequest] = {
            view.as_reference(): view.model_copy(deep=True) for view in self.physical.views
        }

        if include_inherited_properties:
            for ref, view in view_by_reference.items():
                for ancestor in view_ancestors.get(ref, set()):
                    if ancestor_view := view_by_reference.get(ancestor):
                        if ancestor_view.properties:
                            view.properties.update(ancestor_view.properties)

        return view_by_reference

    @property
    def container_by_reference(self) -> dict[ContainerReference, ContainerRequest]:
        """Get a mapping of container references to their corresponding ContainerRequest objects."""
        return {container.as_reference(): container.model_copy(deep=True) for container in self.physical.containers}

    @property
    def connection_end_node_types(self) -> dict[tuple[ViewReference, str], ViewReference]:
        """Get a mapping of view references to their corresponding ViewRequest objects."""
        view_by_reference = self.view_by_reference(include_inherited_properties=False)
        connection_end_node_types: dict[tuple[ViewReference, str], ViewReference] = {}

        for view_ref, view in view_by_reference.items():
            if not view.properties:
                continue
            for prop_ref, property_ in view.properties.items():
                # direct relation
                if isinstance(property_, ViewCorePropertyRequest) and property_.source:
                    connection_end_node_types[(view_ref, prop_ref)] = property_.source

                # reverse direct relation
                if isinstance(property_, ReverseDirectRelationProperty) and property_.source:
                    connection_end_node_types[(view_ref, prop_ref)] = property_.source

                # edge property
                if isinstance(property_, EdgeProperty) and property_.source:
                    connection_end_node_types[(view_ref, prop_ref)] = property_.source

        return connection_end_node_types

    @property
    def reverse_to_direct_mapping(
        self,
    ) -> dict[tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]]:
        """Get a mapping of reverse direct relations to their corresponding source view and 'through' property."""
        view_by_reference = self.view_by_reference(include_inherited_properties=False)
        bidirectional_connections = {}

        for view_ref, view in view_by_reference.items():
            if not view.properties:
                continue
            for prop_ref, property_ in view.properties.items():
                # reverse direct relation
                if isinstance(property_, ReverseDirectRelationProperty):
                    bidirectional_connections[(view_ref, prop_ref)] = (
                        property_.source,
                        property_.through,
                    )

        return bidirectional_connections
