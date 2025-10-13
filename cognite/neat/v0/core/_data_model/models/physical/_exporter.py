import warnings
from collections import defaultdict
from collections.abc import Collection, Hashable, Sequence
from typing import Any, cast

from cognite.client.data_classes import data_modeling as dm
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import EnumValue as DMSEnumValue
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import (
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)

from cognite.neat.v0.core._client.data_classes.data_modeling import (
    ContainerApplyDict,
    NodeApplyDict,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._constants import (
    COGNITE_SPACES,
    DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
    DMS_PRIMITIVE_LIST_DEFAULT_LIMIT,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType, Double, Enum, Float, LangString, String
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    ContainerEntity,
    ContainerIndexEntity,
    DMSFilter,
    DMSNodeEntity,
    EdgeEntity,
    HasDataFilter,
    NodeTypeFilter,
    PhysicalUnknownEntity,
    ReverseConnectionEntity,
    Undefined,
    UnitEntity,
    ViewEntity,
)
from cognite.neat.v0.core._issues.errors import (
    NeatTypeError,
    NeatValueError,
    ResourceNotFoundError,
)
from cognite.neat.v0.core._issues.warnings import (
    NotSupportedWarning,
    PropertyNotFoundWarning,
)
from cognite.neat.v0.core._issues.warnings.user_modeling import (
    EmptyContainerWarning,
    HasDataFilterOnNoPropertiesViewWarning,
)

from ._verified import (
    PhysicalDataModel,
    PhysicalEnum,
    PhysicalMetadata,
    PhysicalProperty,
    PhysicalView,
)


class _DMSExporter:
    """The DMS Exporter is responsible for exporting the physical data model to a DMSSchema.

    This kept in this location such that it can be used by the physical data model to validate the schema.
    (This module cannot have a dependency on the exporter module, as it would create a circular dependency.)

    Args
        include_pipeline (bool): If True, the pipeline will be included with the schema. Pipeline means the
            raw tables and transformations necessary to populate the data model.
        instance_space (str): The space to use for the instance. Defaults to None,`
            PhysicalDataModel.metadata.space` will be used
        remove_cdf_spaces(bool): The
    """

    def __init__(
        self,
        data_model: PhysicalDataModel,
        instance_space: str | None = None,
        remove_cdf_spaces: bool = False,
    ):
        self.instance_space = instance_space
        self.data_model = data_model
        self.remove_cdf_spaces = remove_cdf_spaces

    def to_schema(self) -> DMSSchema:
        data_model = self.data_model
        container_properties_by_id, view_properties_by_id = self._gather_properties(list(self.data_model.properties))

        containers = self._create_containers(container_properties_by_id, data_model.enum)  # type: ignore[arg-type]

        view_properties_with_ancestors_by_id = self._gather_properties_with_ancestors(
            view_properties_by_id, data_model.views
        )

        views = self._create_views(view_properties_by_id, view_properties_with_ancestors_by_id)
        view_node_type_filters: set[dm.NodeId] = set()
        for dms_view in data_model.views:
            if isinstance(dms_view.filter_, NodeTypeFilter):
                view_node_type_filters.update(node.as_id() for node in dms_view.filter_.inner or [])
        if data_model.nodes:
            node_types = NodeApplyDict(
                [node.as_node() for node in data_model.nodes]
                + [dm.NodeApply(node.space, node.external_id) for node in view_node_type_filters]
            )
        else:
            node_types = NodeApplyDict(
                [
                    dm.NodeApply(node.space, node.external_id)
                    for node in view_node_type_filters
                    if not (self.remove_cdf_spaces and node.space in COGNITE_SPACES)
                ]
            )

        dms_data_model = data_model.metadata.as_data_model()
        # Sorting to ensure deterministic order
        dms_data_model.views = sorted(
            [dms_view.view.as_id() for dms_view in data_model.views if dms_view.in_model],
            key=lambda x: x.as_tuple(),  # type: ignore[union-attr]
        )
        spaces = self._create_spaces(data_model.metadata, containers, views, dms_data_model)

        return DMSSchema(
            spaces=spaces,
            data_model=dms_data_model,
            views=views,
            containers=containers,
            node_types=node_types,
        )

    def _create_spaces(
        self,
        metadata: PhysicalMetadata,
        containers: ContainerApplyDict,
        views: ViewApplyDict,
        data_model: dm.DataModelApply,
    ) -> SpaceApplyDict:
        used_spaces = (
            {container.space for container in containers.values()}
            | {view.space for view in views.values()}
            | {data_model.space}
            | {metadata.space}
        )

        spaces = SpaceApplyDict([dm.SpaceApply(space=space) for space in used_spaces])
        if self.instance_space and self.instance_space not in spaces:
            spaces[self.instance_space] = dm.SpaceApply(space=self.instance_space, name=self.instance_space)
        return spaces

    def _create_views(
        self,
        view_properties_by_id: dict[dm.ViewId, list[PhysicalProperty]],
        view_properties_with_ancestors_by_id: dict[dm.ViewId, list[PhysicalProperty]],
    ) -> ViewApplyDict:
        input_views = list(self.data_model.views)

        views = ViewApplyDict(
            [
                dms_view.as_view()
                for dms_view in input_views
                if not (self.remove_cdf_spaces and dms_view.view.space in COGNITE_SPACES)
            ]
        )
        view_by_id = {dms_view.view: dms_view for dms_view in input_views}

        edge_types_by_view_property_id = self._edge_types_by_view_property_id(
            view_properties_with_ancestors_by_id, view_by_id
        )

        for view_id, view in views.items():
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property = self._create_view_property(
                    prop, view_properties_with_ancestors_by_id, edge_types_by_view_property_id
                )
                if view_property is not None:
                    view.properties[prop.view_property] = view_property

        return views

    @classmethod
    def _create_edge_type_from_prop(cls, prop: PhysicalProperty) -> dm.DirectRelationReference:
        if isinstance(prop.connection, EdgeEntity) and prop.connection.edge_type is not None:
            return prop.connection.edge_type.as_reference()
        elif isinstance(prop.value_type, ViewEntity):
            return cls._default_edge_type_from_view_id(prop.view.as_id(), prop.view_property)
        else:
            raise NeatTypeError(f"Invalid valueType {prop.value_type!r}")

    @staticmethod
    def _default_edge_type_from_view_id(view_id: dm.ViewId, property_: str) -> dm.DirectRelationReference:
        return dm.DirectRelationReference(
            space=view_id.space,
            # This is the same convention as used when converting GraphQL to DMS
            external_id=f"{view_id.external_id}.{property_}",
        )

    @classmethod
    def _edge_types_by_view_property_id(
        cls,
        view_properties_with_ancestors_by_id: dict[dm.ViewId, list[PhysicalProperty]],
        view_by_id: dict[ViewEntity, PhysicalView],
    ) -> dict[tuple[ViewEntity, str], dm.DirectRelationReference]:
        edge_connection_property_by_view_property_id: dict[tuple[ViewEntity, str], PhysicalProperty] = {}
        for properties in view_properties_with_ancestors_by_id.values():
            for prop in properties:
                if isinstance(prop.connection, EdgeEntity):
                    view_property_id = (prop.view, prop.view_property)
                    edge_connection_property_by_view_property_id[view_property_id] = prop

        edge_types_by_view_property_id: dict[tuple[ViewEntity, str], dm.DirectRelationReference] = {}

        outwards_type_by_view_value_type: dict[tuple[ViewEntity, ViewEntity], list[dm.DirectRelationReference]] = (
            defaultdict(list)
        )
        # First set the edge types for outwards connections.
        for (view_id, _), prop in edge_connection_property_by_view_property_id.items():
            # We have already filtered out all non-EdgeEntity connections
            connection = cast(EdgeEntity, prop.connection)
            if connection.direction == "inwards":
                continue
            view = view_by_id[view_id]

            edge_type = cls._get_edge_type_outwards_connection(
                view, prop, view_by_id, edge_connection_property_by_view_property_id
            )

            edge_types_by_view_property_id[(prop.view, prop.view_property)] = edge_type

            if isinstance(prop.value_type, ViewEntity):
                outwards_type_by_view_value_type[(prop.value_type, prop.view)].append(edge_type)

        # Then inwards connections = outwards connections
        for (view_id, prop_id), prop in edge_connection_property_by_view_property_id.items():
            # We have already filtered out all non-EdgeEntity connections
            connection = cast(EdgeEntity, prop.connection)

            if connection.direction == "inwards" and isinstance(prop.value_type, ViewEntity):
                edge_type_candidates = outwards_type_by_view_value_type.get((prop.view, prop.value_type), [])
                if len(edge_type_candidates) == 0:
                    # Warning in validation, should not have an inwards connection without an outwards connection
                    edge_type = cls._default_edge_type_from_view_id(prop.view.as_id(), prop_id)
                elif len(edge_type_candidates) == 1:
                    edge_type = edge_type_candidates[0]
                else:
                    raise NeatValueError(
                        f"Cannot infer edge type for {view_id}.{prop_id}, multiple candidates: {edge_type_candidates}."
                        "Please specify edge type explicitly, i.e., edge(type=<YOUR_TYPE>)."
                    )
                view_property_id = (prop.view, prop.view_property)
                edge_types_by_view_property_id[view_property_id] = edge_type

        return edge_types_by_view_property_id

    @classmethod
    def _get_edge_type_outwards_connection(
        cls,
        view: PhysicalView,
        prop: PhysicalProperty,
        view_by_id: dict[ViewEntity, PhysicalView],
        edge_connection_by_view_property_id: dict[tuple[ViewEntity, str], PhysicalProperty],
    ) -> dm.DirectRelationReference:
        connection = cast(EdgeEntity, prop.connection)
        if connection.edge_type is not None:
            # Explicitly set edge type
            return connection.edge_type.as_reference()
        elif view.implements:
            # Try to look for same property in parent views
            candidates = []
            for parent_id in view.implements:
                if parent_view := view_by_id.get(parent_id):
                    parent_prop = edge_connection_by_view_property_id.get((parent_view.view, prop.view_property))
                    if parent_prop and isinstance(parent_prop.connection, EdgeEntity):
                        parent_edge_type = cls._get_edge_type_outwards_connection(
                            parent_view, parent_prop, view_by_id, edge_connection_by_view_property_id
                        )
                        candidates.append(parent_edge_type)
            if len(candidates) == 0:
                return cls._default_edge_type_from_view_id(prop.view.as_id(), prop.view_property)
            elif len(candidates) == 1:
                return candidates[0]
            else:
                raise NeatValueError(
                    f"Cannot infer edge type for {prop.view.as_id()!r}.{prop.view_property}, "
                    f"multiple candidates: {candidates}. "
                    "Please specify edge type explicitly, i.e., edge(type=<YOUR_TYPE>)."
                )
        else:
            # No parent view, use the default
            return cls._default_edge_type_from_view_id(prop.view.as_id(), prop.view_property)

    def _create_containers(
        self,
        container_properties_by_id: dict[dm.ContainerId, list[PhysicalProperty]],
        enum: Collection[PhysicalEnum] | None,
    ) -> ContainerApplyDict:
        enum_values_by_collection: dict[ConceptEntity, list[PhysicalEnum]] = defaultdict(list)
        for enum_value in enum or []:
            enum_values_by_collection[enum_value.collection].append(enum_value)

        containers = list(self.data_model.containers or [])

        containers = dm.ContainerApplyList(
            [
                dms_container.as_container()
                for dms_container in containers
                if not (self.remove_cdf_spaces and dms_container.container.space in COGNITE_SPACES)
            ]
        )
        container_to_drop = set()
        for container in containers:
            container_id = container.as_id()
            if not (container_properties := container_properties_by_id.get(container_id)):
                if container_id.space not in COGNITE_SPACES:
                    warnings.warn(
                        EmptyContainerWarning(container_id),
                        stacklevel=2,
                    )
                container_to_drop.add(container_id)
                continue
            for prop in container_properties:
                if prop.container_property is None:
                    continue
                if isinstance(prop.value_type, DataType):
                    type_cls = prop.value_type.dms
                else:
                    type_cls = dm.DirectRelation

                args: dict[str, Any] = {}
                if issubclass(type_cls, ListablePropertyType):
                    is_list = args["is_list"] = prop.is_list or False
                    if is_list:
                        if type_cls is dm.DirectRelation and prop.max_count == DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT:
                            # Use default of API.
                            args["max_list_size"] = None
                        elif type_cls is not dm.DirectRelation and prop.max_count == DMS_PRIMITIVE_LIST_DEFAULT_LIMIT:
                            # Use default of API.
                            args["max_list_size"] = None
                        else:
                            args["max_list_size"] = prop.max_count
                if isinstance(prop.value_type, Double | Float) and isinstance(prop.value_type.unit, UnitEntity):
                    args["unit"] = prop.value_type.unit.as_reference()
                if isinstance(prop.value_type, String | LangString) and prop.value_type.max_text_size is not None:
                    args["max_text_size"] = prop.value_type.max_text_size
                if isinstance(prop.value_type, Enum):
                    if prop.value_type.collection not in enum_values_by_collection:
                        raise ResourceNotFoundError(
                            prop.value_type.collection, "enum collection", prop.container, "container"
                        )
                    args["unknown_value"] = prop.value_type.unknown_value
                    args["values"] = {
                        value.value: DMSEnumValue(
                            name=value.name,
                            description=value.description,
                        )
                        for value in enum_values_by_collection[prop.value_type.collection]
                    }

                type_ = type_cls(**args)
                container.properties[prop.container_property] = dm.ContainerProperty(
                    type=type_,
                    # If not set, nullable is True and immutable is False
                    nullable=prop.nullable if prop.nullable is not None else True,
                    immutable=prop.immutable if prop.immutable is not None else False,
                    # Guarding against default value being set for connection properties
                    default_value=prop.default if not prop.connection else None,
                    name=prop.name,
                    description=prop.description,
                )

            uniqueness_properties: dict[str, set[str]] = defaultdict(set)
            for prop in container_properties:
                if prop.container_property is not None:
                    for constraint in prop.constraint or []:
                        uniqueness_properties[cast(str, constraint.suffix)].add(prop.container_property)

            for constraint_name, properties in uniqueness_properties.items():
                container.constraints = container.constraints or {}
                container.constraints[constraint_name] = dm.UniquenessConstraint(properties=list(properties))

            index_properties: dict[tuple[str, bool], list[tuple[str, ContainerIndexEntity]]] = defaultdict(list)
            for prop in container_properties:
                if prop.container_property is not None:
                    for index in prop.index or []:
                        index_properties[(index.suffix, prop.is_list or False)].append((prop.container_property, index))
            for (index_name, is_list), properties in index_properties.items():
                container.indexes = container.indexes or {}
                index_property_list = [prop_id for prop_id, _ in sorted(properties, key=lambda x: x[1].order or 0)]
                index_entity = properties[0][1]
                if index_entity.prefix == "inverted" or (index_entity.prefix == Undefined and is_list):
                    container.indexes[index_name] = InvertedIndex(properties=index_property_list)
                elif index_entity.prefix == "btree" or (index_entity.prefix == Undefined and not is_list):
                    container.indexes[index_name] = BTreeIndex(
                        properties=index_property_list, cursorable=index_entity.cursorable or False
                    )
                else:
                    raise NeatValueError(
                        f"Invalid index prefix {index_entity.prefix!r} in {container_id}.{index_entity.suffix!r}"
                    )

        # We might drop containers we convert direct relations of list into multi-edge connections
        # which do not have a container.
        for container in containers:
            if container.constraints:
                container.constraints = {
                    name: const
                    for name, const in container.constraints.items()
                    if not (isinstance(const, dm.RequiresConstraint) and const.require in container_to_drop)
                }
        return ContainerApplyDict([container for container in containers if container.as_id() not in container_to_drop])

    @staticmethod
    def _gather_properties(
        properties: Sequence[PhysicalProperty],
    ) -> tuple[
        dict[dm.ContainerId, list[PhysicalProperty]],
        dict[dm.ViewId, list[PhysicalProperty]],
    ]:
        container_properties_by_id: dict[dm.ContainerId, list[PhysicalProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[PhysicalProperty]] = defaultdict(list)
        for prop in properties:
            view_id = prop.view.as_id()
            view_properties_by_id[view_id].append(prop)

            if prop.container and prop.container_property:
                container_id = prop.container.as_id()
                container_properties_by_id[container_id].append(prop)

        return container_properties_by_id, view_properties_by_id

    def _gather_properties_with_ancestors(
        self,
        view_properties_by_id: dict[dm.ViewId, list[PhysicalProperty]],
        views: Sequence[PhysicalView],
    ) -> dict[dm.ViewId, list[PhysicalProperty]]:
        all_view_properties_by_id = view_properties_by_id.copy()

        view_properties_with_parents_by_id: dict[dm.ViewId, list[PhysicalProperty]] = defaultdict(list)
        view_by_view_id = {view.view.as_id(): view for view in views}
        for view in views:
            view_id = view.view.as_id()
            seen: set[Hashable] = set()
            if view_properties := all_view_properties_by_id.get(view_id):
                view_properties_with_parents_by_id[view_id].extend(view_properties)
                seen.update(prop._identifier() for prop in view_properties)
            if not view.implements:
                continue
            parents = view.implements.copy()
            seen_parents = set(parents)
            while parents:
                parent = parents.pop()
                parent_view_id = parent.as_id()
                if parent_view := view_by_view_id.get(parent_view_id):
                    for grandparent in parent_view.implements or []:
                        if grandparent not in seen_parents:
                            parents.append(grandparent)
                            seen_parents.add(grandparent)

                if not (parent_view_properties := all_view_properties_by_id.get(parent_view_id)):
                    continue
                for prop in parent_view_properties:
                    new_prop = prop.model_copy(update={"view": view.view})

                    if new_prop._identifier() not in seen:
                        view_properties_with_parents_by_id[view_id].append(new_prop)
                        seen.add(new_prop._identifier())

        return view_properties_with_parents_by_id

    @classmethod
    def _update_with_properties(
        cls,
        selected_properties: Sequence[PhysicalProperty],
        container_properties_by_id: dict[dm.ContainerId, list[PhysicalProperty]],
        view_properties_by_id: dict[dm.ViewId, list[PhysicalProperty]] | None,
        include_new_containers: bool = False,
    ) -> None:
        view_properties_by_id = view_properties_by_id or {}
        last_container_properties_by_id, last_view_properties_by_id = cls._gather_properties(selected_properties)

        for container_id, properties in last_container_properties_by_id.items():
            # Only add the container properties that are not already present, and do not overwrite.
            if (container_id in container_properties_by_id) or include_new_containers:
                existing = {prop.container_property for prop in container_properties_by_id.get(container_id, [])}
                container_properties_by_id[container_id].extend(
                    [prop for prop in properties if prop.container_property not in existing]
                )

        if view_properties_by_id:
            for view_id, properties in last_view_properties_by_id.items():
                existing = {prop.view_property for prop in view_properties_by_id[view_id]}
                view_properties_by_id[view_id].extend(
                    [prop for prop in properties if prop.view_property not in existing]
                )

    def _create_view_filter(
        self,
        view: dm.ViewApply,
        dms_view: PhysicalView | None,
    ) -> DMSFilter | None:
        selected_filter_name = (dms_view and dms_view.filter_ and dms_view.filter_.name) or ""

        if dms_view and dms_view.filter_ and not dms_view.filter_.is_empty:
            # Has Explicit Filter, use it
            return dms_view.filter_

        # Enterprise Model or (Solution + HasData)
        ref_containers = view.referenced_containers()
        if not ref_containers or selected_filter_name == HasDataFilter.name:
            # Child filter without container properties
            if selected_filter_name == HasDataFilter.name:
                warnings.warn(
                    HasDataFilterOnNoPropertiesViewWarning(view.as_id()),
                    stacklevel=2,
                )
            return NodeTypeFilter(inner=[DMSNodeEntity(space=view.space, externalId=view.external_id)])
        else:
            # HasData or not provided (this is the default)
            return HasDataFilter(inner=[ContainerEntity.from_id(id_) for id_ in ref_containers])

    @classmethod
    def _create_view_property(
        cls,
        prop: PhysicalProperty,
        view_properties_with_ancestors_by_id: dict[dm.ViewId, list[PhysicalProperty]],
        edge_types_by_view_property_id: dict[tuple[ViewEntity, str], dm.DirectRelationReference],
    ) -> ViewPropertyApply | None:
        if prop.container and prop.container_property:
            return cls._create_mapped_property(prop)
        elif isinstance(prop.connection, EdgeEntity):
            return cls._create_edge_property(prop, edge_types_by_view_property_id)
        elif isinstance(prop.connection, ReverseConnectionEntity):
            return cls._create_reverse_direct_relation(prop, view_properties_with_ancestors_by_id)
        elif prop.view and prop.view_property and prop.connection:
            warnings.warn(
                NotSupportedWarning(f"{prop.connection} in {prop.view.as_id()!r}.{prop.view_property}"),
                stacklevel=2,
            )
        return None

    @classmethod
    def _create_mapped_property(cls, prop: PhysicalProperty) -> dm.MappedPropertyApply:
        container = cast(ContainerEntity, prop.container)
        container_prop_identifier = cast(str, prop.container_property)
        extra_args: dict[str, Any] = {}
        if prop.connection == "direct":
            if isinstance(prop.value_type, ViewEntity):
                extra_args["source"] = prop.value_type.as_id()
            elif isinstance(prop.value_type, PhysicalUnknownEntity):
                extra_args["source"] = None
            else:
                # Should have been validated.
                raise ValueError(
                    "If this error occurs it is a bug in NEAT, please report"
                    f"Debug Info, Invalid valueType direct: {prop.model_dump_json()}"
                )
        elif prop.connection is not None:
            # Should have been validated.
            raise ValueError(
                "If this error occurs it is a bug in NEAT, please report"
                f"Debug Info, Invalid connection: {prop.model_dump_json()}"
            )
        return dm.MappedPropertyApply(
            container=container.as_id(),
            container_property_identifier=container_prop_identifier,
            name=prop.name,
            description=prop.description,
            **extra_args,
        )

    @classmethod
    def _create_edge_property(
        cls,
        prop: PhysicalProperty,
        edge_types_by_view_property_id: dict[tuple[ViewEntity, str], dm.DirectRelationReference],
    ) -> dm.EdgeConnectionApply:
        connection = cast(EdgeEntity, prop.connection)
        if isinstance(prop.value_type, ViewEntity):
            source_view_id = prop.value_type.as_id()
        else:
            # Should have been validated.
            raise ValueError(
                "If this error occurs it is a bug in NEAT, please report"
                f"Debug Info, Invalid valueType edge: {prop.model_dump_json()}"
            )
        edge_source: dm.ViewId | None = None
        if connection.properties is not None:
            edge_source = connection.properties.as_id()
        edge_cls: type[dm.EdgeConnectionApply] = dm.MultiEdgeConnectionApply
        # If is_list is not set, we default to a MultiEdgeConnection
        if prop.is_list is False:
            edge_cls = SingleEdgeConnectionApply

        return edge_cls(
            type=edge_types_by_view_property_id[(prop.view, prop.view_property)],
            source=source_view_id,
            direction=connection.direction,
            name=prop.name,
            description=prop.description,
            edge_source=edge_source,
        )

    @classmethod
    def _create_reverse_direct_relation(
        cls,
        prop: PhysicalProperty,
        view_properties_with_ancestors_by_id: dict[dm.ViewId, list[PhysicalProperty]],
    ) -> dm.MultiReverseDirectRelationApply | SingleReverseDirectRelationApply | None:
        connection = cast(ReverseConnectionEntity, prop.connection)
        reverse_prop_id = connection.property_
        if isinstance(prop.value_type, ViewEntity):
            source_view_id = prop.value_type.as_id()
        else:
            # Should have been validated.
            raise ValueError(
                "If this error occurs it is a bug in NEAT, please report"
                f"Debug Info, Invalid valueType reverse connection: {prop.model_dump_json()}"
            )
        reverse_prop = next(
            (
                prop
                for prop in view_properties_with_ancestors_by_id.get(source_view_id, [])
                if prop.view_property == reverse_prop_id
            ),
            None,
        )
        if reverse_prop is None:
            warnings.warn(
                PropertyNotFoundWarning(
                    source_view_id,
                    "view",
                    reverse_prop_id or "MISSING",
                    dm.PropertyId(prop.view.as_id(), prop.view_property),
                    "view property",
                ),
                stacklevel=2,
            )

        if reverse_prop and reverse_prop.connection == "direct":
            args: dict[str, Any] = dict(
                source=source_view_id,
                through=dm.PropertyId(source=source_view_id, property=reverse_prop_id),
                name=prop.name,
                description=prop.description,
            )
            if prop.is_list in [True, None]:
                return dm.MultiReverseDirectRelationApply(**args)
            else:
                return SingleReverseDirectRelationApply(**args)
        else:
            return None
