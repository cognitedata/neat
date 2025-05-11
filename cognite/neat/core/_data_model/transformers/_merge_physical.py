from collections.abc import Iterable
from typing import Literal

from cognite.neat.core._data_model.models import DMSRules, SheetList
from cognite.neat.core._data_model.models.data_types import Enum
from cognite.neat.core._data_model.models.dms import DMSContainer, DMSEnum, DMSNode, DMSProperty, DMSView
from cognite.neat.core._data_model.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSNodeEntity,
    EdgeEntity,
    NodeTypeFilter,
    ViewEntity,
)
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer
from cognite.neat.core._issues.errors import NeatValueError


class MergeDMSRules(VerifiedRulesTransformer[DMSRules, DMSRules]):
    """Merges two DMS rules into one.

    Args:
        secondary: The secondary model. The primary model is the one that is passed to the transform method.
        join: The join strategy for merging views. To only keep views from the primary model, use "primary".
            To only keep views from the secondary model, use "secondary". To keep all views, use "combined".
        priority: For properties that exist in both models, the priority determines which model's property is kept.
            For example, if 'name' of a property exists in both models, and the priority is set to "primary",
            the property from the primary model will be kept.
        conflict_resolution: The conflict resolution strategy for merging views. This applies to fields that
            can be combined, such as view.implements. If set to "combine", the implements list will be combined
            to include all implements from both models. If set to "priority", the implements list will be
            given by the 'priority' argument.
    """

    def __init__(
        self,
        secondary: DMSRules,
        join: Literal["primary", "secondary", "combined"] = "combined",
        priority: Literal["primary", "secondary"] = "primary",
        conflict_resolution: Literal["priority", "combine"] = "priority",
    ) -> None:
        self.secondary = secondary
        self.join = join
        self.priority = priority
        self.conflict_resolution = conflict_resolution

    @property
    def description(self) -> str:
        return f"Merged with {self.secondary.metadata.as_data_model_id()}"

    def transform(self, rules: DMSRules) -> DMSRules:
        if self.join in ["primary", "combined"]:
            output = rules.model_copy(deep=True)
            secondary_views = {view.view: view for view in self.secondary.views}
            secondary_properties = {(prop.view, prop.view_property): prop for prop in self.secondary.properties}
            secondary_containers = {container.container: container for container in self.secondary.containers or []}
            secondary_nodes = {node.node: node for node in self.secondary.nodes or []}
            secondary_enum = {(enum.collection, enum.value): enum for enum in self.secondary.enum or []}
        elif self.join == "secondary":
            output = self.secondary.model_copy(deep=True)
            secondary_views = {view.view: view for view in rules.views}
            secondary_properties = {(prop.view, prop.view_property): prop for prop in rules.properties}
            secondary_containers = {container.container: container for container in rules.containers or []}
            secondary_nodes = {node.node: node for node in rules.nodes or []}
            secondary_enum = {(enum.collection, enum.value): enum for enum in rules.enum or []}
        else:
            raise NeatValueError(
                f"Invalid join strategy: {self.join}. Must be one of ['primary', 'secondary', 'combined']"
            )
        merged_views_by_id = self._merge_views(output.views, secondary_views)
        output.views = SheetList[DMSView](merged_views_by_id.values())

        merged_properties = self._merge_properties(
            output.properties, secondary_properties, set(merged_views_by_id.keys())
        )
        output.properties = SheetList[DMSProperty](merged_properties.values())

        used_containers = {prop.container for prop in output.properties if prop.container}
        merged_containers = self._merge_containers(output.containers or [], secondary_containers, used_containers)
        output.containers = SheetList[DMSContainer](merged_containers.values()) or None

        used_nodes = self._get_used_nodes(output.views, output.properties)
        merged_nodes = self._merge_nodes(output.nodes or [], secondary_nodes, used_nodes)
        output.nodes = SheetList[DMSNode](merged_nodes.values()) or None

        used_enum_collections = self._get_used_enum_collections(output.properties)
        merged_enum = self._merge_enum(output.enum or [], secondary_enum, used_enum_collections)
        output.enum = SheetList[DMSEnum](merged_enum.values()) or None

        return output

    @property
    def _swap_priority(self) -> bool:
        """We swap the priority if 'join' and 'priority' are mismatched. For example, if
        we use a 'primary' join strategy, i.e., selecting classes from the primary model, but prioritize the
        secondary classes that matches the primary classes.
        """

        return (self.priority == "secondary" and (self.join in ["primary", "combined"])) or (
            self.priority == "primary" and (self.join == "secondary")
        )

    def _merge_views(
        self,
        primary_views: Iterable[DMSView],
        secondary_views: dict[ViewEntity, DMSView],
    ) -> dict[ViewEntity, DMSView]:
        merged_views = {view.view: view for view in primary_views}
        for view, primary in merged_views.items():
            if view not in secondary_views:
                continue
            secondary = secondary_views[view]
            if self._swap_priority:
                primary, secondary = primary, secondary
            merged_views[view] = self.merge_views(primary, secondary)

        if self.join == "combined":
            for view, secondary in secondary_views.items():
                if view in merged_views:
                    continue
                merged_views[view] = secondary
        return merged_views

    def _merge_properties(
        self,
        primary_properties: Iterable[DMSProperty],
        secondary_properties: dict[tuple[ViewEntity, str], DMSProperty],
        used_views: set[ViewEntity],
    ) -> dict[tuple[ViewEntity, str], DMSProperty]:
        merged_properties = {(prop.view, prop.view_property): prop for prop in primary_properties}
        for (view, prop), primary in merged_properties.items():
            if ((view, prop) not in secondary_properties) or (view not in used_views):
                continue
            secondary = secondary_properties[(view, prop)]
            if self._swap_priority:
                primary, secondary = secondary, primary
            merged_properties[(view, prop)] = self.merge_properties(primary, secondary)

        if self.join == "combined":
            for (view, prop), secondary in secondary_properties.items():
                if ((view, prop) not in merged_properties) and view in used_views:
                    merged_properties[(view, prop)] = secondary
        return merged_properties

    def _merge_containers(
        self,
        primary_containers: Iterable[DMSContainer],
        secondary_containers: dict[ContainerEntity, DMSContainer],
        used_containers: set[ContainerEntity],
    ) -> dict[ContainerEntity, DMSContainer]:
        merged_containers = {container.container: container for container in primary_containers}
        for container, primary in merged_containers.items():
            if (container not in secondary_containers) or (container not in used_containers):
                continue
            secondary = secondary_containers[container]
            if self._swap_priority:
                primary, secondary = secondary, primary
            merged_containers[container] = self.merge_containers(primary, secondary)

        if self.join == "combined":
            for container, secondary in secondary_containers.items():
                if (container not in merged_containers) and (container in used_containers):
                    merged_containers[container] = secondary
        return merged_containers

    @staticmethod
    def _get_used_nodes(views: SheetList[DMSView], properties: SheetList[DMSProperty]) -> set[DMSNodeEntity]:
        """Get the set of used nodes from views and properties."""
        used_nodes: set[DMSNodeEntity] = set()
        for view in views:
            if isinstance(view.filter_, NodeTypeFilter):
                used_nodes.update(view.filter_.inner or [])
        for prop in properties:
            if isinstance(prop.connection, EdgeEntity):
                if prop.connection.edge_type:
                    used_nodes.add(prop.connection.edge_type)
        return used_nodes

    def _merge_nodes(
        self,
        primary_nodes: Iterable[DMSNode],
        secondary_nodes: dict[DMSNodeEntity, DMSNode],
        used_nodes: set[DMSNodeEntity],
    ) -> dict[DMSNodeEntity, DMSNode]:
        merged_nodes = {node.node: node for node in primary_nodes}
        for node, primary in merged_nodes.items():
            if (node not in secondary_nodes) or (node not in used_nodes):
                continue
            secondary = secondary_nodes[node]
            if self._swap_priority:
                primary, secondary = secondary, primary
            merged_nodes[node] = self.merge_nodes(primary, secondary)

        if self.join == "combined":
            for node, secondary in secondary_nodes.items():
                if (node not in merged_nodes) and (node in used_nodes):
                    merged_nodes[node] = secondary
        return merged_nodes

    @staticmethod
    def _get_used_enum_collections(properties: SheetList[DMSProperty]) -> set[ClassEntity]:
        """Get the set of used enum collections from properties."""
        used_enum_collections: set[ClassEntity] = set()
        for prop in properties:
            if isinstance(prop.value_type, Enum):
                used_enum_collections.add(prop.value_type.collection)
        return used_enum_collections

    def _merge_enum(
        self,
        primary_enum: Iterable[DMSEnum],
        secondary_enum: dict[tuple[ClassEntity, str], DMSEnum],
        used_enum_collections: set[ClassEntity],
    ) -> dict[tuple[ClassEntity, str], DMSEnum]:
        merged_enum = {(enum.collection, enum.value): enum for enum in primary_enum}
        for (collection, value), primary in merged_enum.items():
            if ((collection, value) not in secondary_enum) or (collection not in used_enum_collections):
                continue
            secondary = secondary_enum[(collection, value)]
            if self._swap_priority:
                primary, secondary = secondary, primary
            merged_enum[(collection, value)] = self.merge_enum(primary, secondary)

        if self.join == "combined":
            for (collection, value), secondary in secondary_enum.items():
                if ((collection, value) not in merged_enum) and (collection in used_enum_collections):
                    merged_enum[(collection, value)] = secondary
        return merged_enum

    @classmethod
    def merge_properties(
        cls,
        primary: DMSProperty,
        secondary: DMSProperty,
    ) -> DMSProperty:
        return DMSProperty(
            view=primary.view,
            view_property=primary.view_property,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
            connection=primary.connection,
            value_type=primary.value_type,
            min_count=primary.min_count,
            max_count=primary.max_count,
            immutable=primary.immutable,
            default=primary.default,
            container=primary.container,
            container_property=primary.container_property,
            index=primary.index,
            constraint=primary.constraint,
            logical=primary.logical,
        )

    @classmethod
    def merge_views(
        cls,
        primary: DMSView,
        secondary: DMSView,
        conflict_resolution: Literal["priority", "combine"] = "priority",
    ) -> DMSView:
        # Combined = merge implements for both classes
        # Priority = keep the primary with fallback to secondary
        implements = (primary.implements or secondary.implements or []).copy()
        if conflict_resolution == "combined":
            seen = set(implements)
            for cls_ in secondary.implements or []:
                if cls_ not in seen:
                    seen.add(cls_)
                    implements.append(cls_)
        return DMSView(
            neatId=primary.neatId,
            view=primary.view,
            implements=implements,
            filter_=primary.filter_,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
            logical=primary.logical,
            in_model=primary.in_model,
        )

    @classmethod
    def merge_containers(
        cls,
        primary: DMSContainer,
        secondary: DMSContainer,
    ) -> DMSContainer:
        return DMSContainer(
            neatId=primary.neatId,
            container=primary.container,
            constraint=primary.constraint,
            used_for=primary.used_for,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
        )

    @classmethod
    def merge_nodes(
        cls,
        primary: DMSNode,
        secondary: DMSNode,
    ) -> DMSNode:
        return DMSNode(
            neatId=primary.neatId,
            node=primary.node,
            usage=primary.usage,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
        )

    @classmethod
    def merge_enum(
        cls,
        primary: DMSEnum,
        secondary: DMSEnum,
    ) -> DMSEnum:
        return DMSEnum(
            neatId=primary.neatId,
            collection=primary.collection,
            value=primary.value,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
        )
