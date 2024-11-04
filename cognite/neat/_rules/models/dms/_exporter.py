import warnings
from collections import defaultdict
from collections.abc import Collection, Hashable, Sequence
from typing import Any, cast

from cognite.client.data_classes import data_modeling as dm
from cognite.client.data_classes.data_modeling.containers import BTreeIndex
from cognite.client.data_classes.data_modeling.data_types import EnumValue as DMSEnumValue
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import (
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)

from cognite.neat._issues.errors import NeatTypeError, ResourceNotFoundError
from cognite.neat._issues.warnings import NotSupportedWarning, PropertyNotFoundWarning
from cognite.neat._issues.warnings.user_modeling import (
    EmptyContainerWarning,
    HasDataFilterOnNoPropertiesViewWarning,
    HasDataFilterOnViewWithReferencesWarning,
    NodeTypeFilterOnParentViewWarning,
)
from cognite.neat._rules.models._base_rules import DataModelType, ExtensionCategory, SchemaCompleteness
from cognite.neat._rules.models.data_types import DataType, Double, Enum, Float
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSFilter,
    DMSNodeEntity,
    DMSUnknownEntity,
    EdgeEntity,
    HasDataFilter,
    NodeTypeFilter,
    ReferenceEntity,
    ReverseConnectionEntity,
    UnitEntity,
    ViewEntity,
)
from cognite.neat._utils.cdf.data_classes import ContainerApplyDict, NodeApplyDict, SpaceApplyDict, ViewApplyDict

from ._rules import DMSEnum, DMSMetadata, DMSProperty, DMSRules, DMSView
from ._schema import DMSSchema, PipelineSchema


class _DMSExporter:
    """The DMS Exporter is responsible for exporting the DMSRules to a DMSSchema.

    This kept in this location such that it can be used by the DMSRules to validate the schema.
    (This module cannot have a dependency on the exporter module, as it would create a circular dependency.)

    Args
        include_pipeline (bool): If True, the pipeline will be included with the schema. Pipeline means the
            raw tables and transformations necessary to populate the data model.
        instance_space (str): The space to use for the instance. Defaults to None,`Rules.metadata.space` will be used
    """

    def __init__(
        self,
        rules: DMSRules,
        include_pipeline: bool = False,
        instance_space: str | None = None,
    ):
        self.include_pipeline = include_pipeline
        self.instance_space = instance_space
        self.rules = rules
        self._ref_schema = rules.reference.as_schema() if rules.reference else None
        if self._ref_schema:
            # We skip version as that will always be missing in the reference
            self._ref_views_by_id = {
                dm.ViewId(view.space, view.external_id): view for view in self._ref_schema.views.values()
            }
        else:
            self._ref_views_by_id = {}

        self.is_addition = (
            rules.metadata.schema_ is SchemaCompleteness.extended
            and rules.metadata.extension is ExtensionCategory.addition
        )
        self.is_reshape = (
            rules.metadata.schema_ is SchemaCompleteness.extended
            and rules.metadata.extension is ExtensionCategory.reshape
        )
        self.is_rebuild = (
            rules.metadata.schema_ is SchemaCompleteness.extended
            and rules.metadata.extension is ExtensionCategory.rebuild
        )

    def to_schema(self) -> DMSSchema:
        rules = self.rules
        container_properties_by_id, view_properties_by_id = self._gather_properties(list(self.rules.properties))

        # If we are reshaping or rebuilding, and there are no properties in the current rules, we will
        # include those properties from the last rules.
        if rules.last and (self.is_reshape or self.is_rebuild):
            selected_views = {view.view for view in rules.views}
            selected_properties = [
                prop
                for prop in rules.last.properties
                if prop.view in selected_views and prop.view.as_id() not in view_properties_by_id
            ]
            self._update_with_properties(
                selected_properties, container_properties_by_id, view_properties_by_id, include_new_containers=True
            )

        # We need to include the properties from the last rules as well to create complete containers and view
        # depending on the type of extension.
        if rules.last and self.is_addition:
            selected_properties = [
                prop for prop in rules.last.properties if (prop.view.as_id() in view_properties_by_id)
            ]
            self._update_with_properties(selected_properties, container_properties_by_id, view_properties_by_id)
        elif rules.last and (self.is_reshape or self.is_rebuild):
            selected_properties = [
                prop
                for prop in rules.last.properties
                if prop.container and prop.container.as_id() in container_properties_by_id
            ]
            self._update_with_properties(selected_properties, container_properties_by_id, None)

        containers = self._create_containers(container_properties_by_id, rules.enum)  # type: ignore[arg-type]

        view_properties_with_ancestors_by_id = self._gather_properties_with_ancestors(
            view_properties_by_id, rules.views
        )

        views, view_node_type_filters = self._create_views_with_node_types(
            view_properties_by_id, view_properties_with_ancestors_by_id
        )
        if rules.nodes:
            node_types = NodeApplyDict(
                [node.as_node() for node in rules.nodes]
                + [dm.NodeApply(node.space, node.external_id) for node in view_node_type_filters]
            )
        else:
            node_types = NodeApplyDict([dm.NodeApply(node.space, node.external_id) for node in view_node_type_filters])

        last_schema: DMSSchema | None = None
        if self.rules.last:
            last_schema = self.rules.last.as_schema()
            # Remove the views that are in the current model, last + current should equal the full model
            # without any duplicates
            last_schema.views = ViewApplyDict(
                {view_id: view for view_id, view in last_schema.views.items() if view_id not in views}
            )
            last_schema.containers = ContainerApplyDict(
                {
                    container_id: container
                    for container_id, container in last_schema.containers.items()
                    if container_id not in containers
                }
            )

        views_not_in_model = {view.view.as_id() for view in rules.views if not view.in_model}
        if rules.last and self.is_addition:
            views_not_in_model.update({view.view.as_id() for view in rules.last.views if not view.in_model})

        data_model = rules.metadata.as_data_model()

        data_model_views = [view_id for view_id in views if view_id not in views_not_in_model]
        if last_schema and self.is_addition:
            data_model_views.extend([view_id for view_id in last_schema.views if view_id not in views_not_in_model])

        # Sorting to ensure deterministic order
        data_model.views = sorted(data_model_views, key=lambda v: v.as_tuple())  # type: ignore[union-attr]

        spaces = self._create_spaces(rules.metadata, containers, views, data_model)

        output = DMSSchema(
            spaces=spaces,
            data_model=data_model,
            views=views,
            containers=containers,
            node_types=node_types,
        )
        if self.include_pipeline:
            return PipelineSchema.from_dms(output, self.instance_space)

        if self._ref_schema:
            output.reference = self._ref_schema
        if last_schema:
            output.last = last_schema
        return output

    def _create_spaces(
        self,
        metadata: DMSMetadata,
        containers: ContainerApplyDict,
        views: ViewApplyDict,
        data_model: dm.DataModelApply,
    ) -> SpaceApplyDict:
        used_spaces = {container.space for container in containers.values()} | {view.space for view in views.values()}
        if len(used_spaces) == 1:
            # We skip the default space and only use this space for the data model
            data_model.space = used_spaces.pop()
            spaces = SpaceApplyDict([dm.SpaceApply(space=data_model.space)])
        else:
            used_spaces.add(metadata.space)
            spaces = SpaceApplyDict([dm.SpaceApply(space=space) for space in used_spaces])
        if self.instance_space and self.instance_space not in spaces:
            spaces[self.instance_space] = dm.SpaceApply(space=self.instance_space, name=self.instance_space)
        return spaces

    def _create_views_with_node_types(
        self,
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]],
        view_properties_with_ancestors_by_id: dict[dm.ViewId, list[DMSProperty]],
    ) -> tuple[ViewApplyDict, set[dm.NodeId]]:
        input_views = list(self.rules.views)
        if self.rules.last:
            existing = {view.view.as_id() for view in input_views}
            modified_views = [
                v
                for v in self.rules.last.views
                if v.view.as_id() in view_properties_by_id and v.view.as_id() not in existing
            ]
            input_views.extend(modified_views)

        views = ViewApplyDict([dms_view.as_view() for dms_view in input_views])
        dms_view_by_id = {dms_view.view.as_id(): dms_view for dms_view in input_views}

        for view_id, view in views.items():
            view.properties = {}
            if not (view_properties := view_properties_by_id.get(view_id)):
                continue
            for prop in view_properties:
                view_property = self._create_view_property(prop, view_properties_with_ancestors_by_id)
                if view_property is not None:
                    view.properties[prop.view_property] = view_property

        data_model_type = self.rules.metadata.data_model_type
        unique_node_types: set[dm.NodeId] = set()
        parent_views = {parent for view in views.values() for parent in view.implements or []}
        for view_id, view in views.items():
            dms_view = dms_view_by_id.get(view_id)
            dms_properties = view_properties_by_id.get(view_id, [])
            view_filter = self._create_view_filter(view, dms_view, data_model_type, dms_properties)

            view.filter = view_filter.as_dms_filter()
            if isinstance(view_filter, NodeTypeFilter):
                unique_node_types.update(view_filter.nodes)
                if view.as_id() in parent_views:
                    warnings.warn(
                        NodeTypeFilterOnParentViewWarning(view.as_id()),
                        stacklevel=2,
                    )

            elif isinstance(view_filter, HasDataFilter) and data_model_type == DataModelType.solution:
                if dms_view and isinstance(dms_view.reference, ReferenceEntity):
                    references = {dms_view.reference.as_view_id()}
                elif any(True for prop in dms_properties if isinstance(prop.reference, ReferenceEntity)):
                    references = {
                        prop.reference.as_view_id()
                        for prop in dms_properties
                        if isinstance(prop.reference, ReferenceEntity)
                    }
                else:
                    continue
                warnings.warn(
                    HasDataFilterOnViewWithReferencesWarning(view.as_id(), frozenset(references)),
                    stacklevel=2,
                )

            if data_model_type == DataModelType.enterprise:
                # Enterprise Model needs to create node types for all views,
                # as they are expected for the solution model.
                unique_node_types.add(dm.NodeId(space=view.space, external_id=view.external_id))

        return views, unique_node_types

    @classmethod
    def _create_edge_type_from_prop(cls, prop: DMSProperty) -> dm.DirectRelationReference:
        if isinstance(prop.connection, EdgeEntity) and prop.connection.edge_type is not None:
            return prop.connection.edge_type.as_reference()
        elif isinstance(prop.reference, ReferenceEntity):
            ref_view_prop = prop.reference.as_view_property_id()
            return cls._create_edge_type_from_view_id(cast(dm.ViewId, ref_view_prop.source), ref_view_prop.property)
        elif isinstance(prop.value_type, ViewEntity):
            return cls._create_edge_type_from_view_id(prop.view.as_id(), prop.view_property)
        else:
            raise NeatTypeError(f"Invalid valueType {prop.value_type!r}")

    @staticmethod
    def _create_edge_type_from_view_id(view_id: dm.ViewId, property_: str) -> dm.DirectRelationReference:
        return dm.DirectRelationReference(
            space=view_id.space,
            # This is the same convention as used when converting GraphQL to DMS
            external_id=f"{view_id.external_id}.{property_}",
        )

    def _create_containers(
        self,
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]],
        enum: Collection[DMSEnum] | None,
    ) -> ContainerApplyDict:
        enum_values_by_collection: dict[ClassEntity, list[DMSEnum]] = defaultdict(list)
        for enum_value in enum or []:
            enum_values_by_collection[enum_value.collection].append(enum_value)

        containers = list(self.rules.containers or [])
        if self.rules.last:
            existing = {container.container.as_id() for container in containers}
            modified_containers = [
                c
                for c in self.rules.last.containers or []
                if c.container.as_id() in container_properties_by_id and c.container.as_id() not in existing
            ]
            containers.extend(modified_containers)

        containers = dm.ContainerApplyList([dms_container.as_container() for dms_container in containers])
        container_to_drop = set()
        for container in containers:
            container_id = container.as_id()
            if not (container_properties := container_properties_by_id.get(container_id)):
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
                    args["is_list"] = prop.is_list or False
                if isinstance(prop.value_type, Double | Float) and isinstance(prop.value_type.unit, UnitEntity):
                    args["unit"] = prop.value_type.unit.as_reference()
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
                        uniqueness_properties[constraint].add(prop.container_property)
            for constraint_name, properties in uniqueness_properties.items():
                container.constraints = container.constraints or {}
                container.constraints[constraint_name] = dm.UniquenessConstraint(properties=list(properties))

            index_properties: dict[str, set[str]] = defaultdict(set)
            for prop in container_properties:
                if prop.container_property is not None:
                    for index in prop.index or []:
                        index_properties[index].add(prop.container_property)
            for index_name, properties in index_properties.items():
                container.indexes = container.indexes or {}
                container.indexes[index_name] = BTreeIndex(properties=list(properties))

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
        properties: Sequence[DMSProperty],
    ) -> tuple[dict[dm.ContainerId, list[DMSProperty]], dict[dm.ViewId, list[DMSProperty]]]:
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]] = defaultdict(list)
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in properties:
            view_id = prop.view.as_id()
            view_properties_by_id[view_id].append(prop)

            if prop.container and prop.container_property:
                container_id = prop.container.as_id()
                container_properties_by_id[container_id].append(prop)

        return container_properties_by_id, view_properties_by_id

    @staticmethod
    def _gather_properties_with_ancestors(
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]],
        views: Sequence[DMSView],
    ) -> dict[dm.ViewId, list[DMSProperty]]:
        view_properties_with_parents_by_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        view_by_view_id = {view.view.as_id(): view for view in views}
        for view in views:
            view_id = view.view.as_id()
            seen: set[Hashable] = set()
            if view_properties := view_properties_by_id.get(view_id):
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

                if not (parent_view_properties := view_properties_by_id.get(parent_view_id)):
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
        selected_properties: Sequence[DMSProperty],
        container_properties_by_id: dict[dm.ContainerId, list[DMSProperty]],
        view_properties_by_id: dict[dm.ViewId, list[DMSProperty]] | None,
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
        dms_view: DMSView | None,
        data_model_type: DataModelType,
        dms_properties: list[DMSProperty],
    ) -> DMSFilter:
        selected_filter_name = (dms_view and dms_view.filter_ and dms_view.filter_.name) or ""

        if dms_view and dms_view.filter_ and not dms_view.filter_.is_empty:
            # Has Explicit Filter, use it
            return dms_view.filter_

        if data_model_type == DataModelType.solution and selected_filter_name in [NodeTypeFilter.name, ""]:
            if (
                dms_view
                and isinstance(dms_view.reference, ReferenceEntity)
                and not dms_properties
                and (ref_view := self._ref_views_by_id.get(dms_view.reference.as_view_id()))
                and ref_view.filter
            ):
                # No new properties, only reference, reuse the reference filter
                return DMSFilter.from_dms_filter(ref_view.filter)
            else:
                referenced_node_ids = {
                    prop.reference.as_node_entity()
                    for prop in dms_properties
                    if isinstance(prop.reference, ReferenceEntity)
                }
                if dms_view and isinstance(dms_view.reference, ReferenceEntity):
                    referenced_node_ids.add(dms_view.reference.as_node_entity())

                if referenced_node_ids:
                    return NodeTypeFilter(inner=list(referenced_node_ids))

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
        cls, prop: DMSProperty, view_properties_with_ancestors_by_id: dict[dm.ViewId, list[DMSProperty]]
    ) -> ViewPropertyApply | None:
        if prop.container and prop.container_property:
            container_prop_identifier = prop.container_property
            extra_args: dict[str, Any] = {}
            if prop.connection == "direct":
                if isinstance(prop.value_type, ViewEntity):
                    extra_args["source"] = prop.value_type.as_id()
                elif isinstance(prop.value_type, DMSUnknownEntity):
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
                container=prop.container.as_id(),
                container_property_identifier=container_prop_identifier,
                name=prop.name,
                description=prop.description,
                **extra_args,
            )
        elif isinstance(prop.connection, EdgeEntity):
            if isinstance(prop.value_type, ViewEntity):
                source_view_id = prop.value_type.as_id()
            else:
                # Should have been validated.
                raise ValueError(
                    "If this error occurs it is a bug in NEAT, please report"
                    f"Debug Info, Invalid valueType edge: {prop.model_dump_json()}"
                )
            edge_source: dm.ViewId | None = None
            if prop.connection.properties is not None:
                edge_source = prop.connection.properties.as_id()
            edge_cls: type[dm.EdgeConnectionApply] = dm.MultiEdgeConnectionApply
            # If is_list is not set, we default to a MultiEdgeConnection
            if prop.is_list is False:
                edge_cls = SingleEdgeConnectionApply

            return edge_cls(
                type=cls._create_edge_type_from_prop(prop),
                source=source_view_id,
                direction=prop.connection.direction,
                name=prop.name,
                description=prop.description,
                edge_source=edge_source,
            )
        elif isinstance(prop.connection, ReverseConnectionEntity):
            reverse_prop_id = prop.connection.property_
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
                    if prop.property_ == reverse_prop_id
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

        elif prop.view and prop.view_property and prop.connection:
            warnings.warn(
                NotSupportedWarning(f"{prop.connection} in {prop.view.as_id()!r}.{prop.view_property}"), stacklevel=2
            )
        return None
