import warnings
from abc import ABC
from collections import defaultdict
from functools import cached_property
from typing import Any, ClassVar, Literal

from cognite.client import data_modeling as dm

from cognite.neat._client import NeatClient
from cognite.neat._issues.errors import CDFMissingClientError, NeatValueError, ResourceNotFoundError
from cognite.neat._issues.warnings import NeatValueWarning, PropertyOverwritingWarning
from cognite.neat._rules._shared import JustRules, OutRules
from cognite.neat._rules.models import DMSRules, SheetList
from cognite.neat._rules.models.data_types import Enum
from cognite.neat._rules.models.dms import DMSEnum, DMSProperty, DMSView
from cognite.neat._rules.models.entities import ContainerEntity, ViewEntity

from ._base import RulesTransformer


class MapOntoTransformers(RulesTransformer[DMSRules, DMSRules], ABC):
    """Base class for transformers that map one rule onto another."""

    ...


class MapOneToOne(MapOntoTransformers):
    """Takes transform data models and makes it into an extension of the reference data model.

    Note this transformer mutates the input rules.

    The argument view_extension_mapping is a dictionary where the keys are views of this data model,
    and each value is the view of the reference data model that the view should extend. For example:

    ```python
    view_extension_mapping = {"Pump": "Asset"}
    ```

    This would make the view "Pump" in this data model extend the view "Asset" in the reference data model.
    Note that all the keys in the dictionary must be external ids of views in this data model,
    and all the values must be external ids of views in the reference data model.

    Args:
        reference: The reference data model
        view_extension_mapping: A dictionary mapping views in this data model to views in the reference data model
        default_extension: The default view in the reference data model that views in this
            data model should extend if no mapping is provided.

    """

    def __init__(
        self, reference: DMSRules, view_extension_mapping: dict[str, str], default_extension: str | None = None
    ) -> None:
        self.reference = reference
        self.view_extension_mapping = view_extension_mapping
        self.default_extension = default_extension

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        solution: DMSRules = self._to_rules(rules)
        view_by_external_id = {view.view.external_id: view for view in solution.views}
        ref_view_by_external_id = {view.view.external_id: view for view in self.reference.views}

        if invalid_views := set(self.view_extension_mapping.keys()) - set(view_by_external_id.keys()):
            raise ValueError(f"Views are not in this dat model {invalid_views}")
        if invalid_views := set(self.view_extension_mapping.values()) - set(ref_view_by_external_id.keys()):
            raise ValueError(f"Views are not in the reference data model {invalid_views}")
        if self.default_extension and self.default_extension not in ref_view_by_external_id:
            raise ValueError(f"Default extension view not in the reference data model {self.default_extension}")

        properties_by_view_external_id: dict[str, dict[str, DMSProperty]] = defaultdict(dict)
        for prop in solution.properties:
            properties_by_view_external_id[prop.view.external_id][prop.view_property] = prop

        ref_properties_by_view_external_id: dict[str, dict[str, DMSProperty]] = defaultdict(dict)
        for prop in self.reference.properties:
            ref_properties_by_view_external_id[prop.view.external_id][prop.view_property] = prop

        for view_external_id, view in view_by_external_id.items():
            if view_external_id in self.view_extension_mapping:
                ref_external_id = self.view_extension_mapping[view_external_id]
            elif self.default_extension:
                ref_external_id = self.default_extension
            else:
                continue

            ref_view = ref_view_by_external_id[ref_external_id]
            shared_properties = set(properties_by_view_external_id[view_external_id].keys()) & set(
                ref_properties_by_view_external_id[ref_external_id].keys()
            )
            if shared_properties:
                if view.implements is None:
                    view.implements = [ref_view.view]
                elif isinstance(view.implements, list) and ref_view.view not in view.implements:
                    view.implements.append(ref_view.view)
            for prop_name in shared_properties:
                prop = properties_by_view_external_id[view_external_id][prop_name]
                ref_prop = ref_properties_by_view_external_id[ref_external_id][prop_name]
                if ref_prop.container and ref_prop.container_property:
                    prop.container = ref_prop.container
                    prop.container_property = ref_prop.container_property

        return JustRules(solution)


class RuleMapper(RulesTransformer[DMSRules, DMSRules]):
    """Maps properties and classes using the given mapping.

    **Note**: This transformer mutates the input rules.

    Args:
        mapping: The mapping to use.

    """

    _mapping_fields: ClassVar[frozenset[str]] = frozenset(
        ["connection", "value_type", "nullable", "immutable", "is_list", "default", "index", "constraint"]
    )

    def __init__(self, mapping: DMSRules, data_type_conflict: Literal["overwrite"] = "overwrite") -> None:
        self.mapping = mapping
        self.data_type_conflict = data_type_conflict

    @cached_property
    def _view_by_entity_id(self) -> dict[str, DMSView]:
        return {view.view.external_id: view for view in self.mapping.views}

    @cached_property
    def _property_by_view_property(self) -> dict[tuple[str, str], DMSProperty]:
        return {(prop.view.external_id, prop.view_property): prop for prop in self.mapping.properties}

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        if self.data_type_conflict != "overwrite":
            raise NeatValueError(f"Invalid data_type_conflict: {self.data_type_conflict}")
        input_rules = self._to_rules(rules)
        new_rules = input_rules.model_copy(deep=True)
        new_rules.metadata.version += "_mapped"

        for view in new_rules.views:
            if mapping_view := self._view_by_entity_id.get(view.view.external_id):
                view.implements = mapping_view.implements

        for prop in new_rules.properties:
            key = (prop.view.external_id, prop.view_property)
            if key not in self._property_by_view_property:
                continue
            mapping_prop = self._property_by_view_property[key]
            to_overwrite, conflicts = self._find_overwrites(prop, mapping_prop)
            if conflicts and self.data_type_conflict == "overwrite":
                warnings.warn(
                    PropertyOverwritingWarning(prop.view.as_id(), "view", prop.view_property, tuple(conflicts)),
                    stacklevel=2,
                )
            elif conflicts:
                raise NeatValueError(f"Conflicting properties for {prop.view}.{prop.view_property}: {conflicts}")
            for field_name, value in to_overwrite.items():
                setattr(prop, field_name, value)
            prop.container = mapping_prop.container
            prop.container_property = mapping_prop.container_property

        # Add missing views used as value types
        existing_views = {view.view for view in new_rules.views}
        new_value_types = {
            prop.value_type
            for prop in new_rules.properties
            if isinstance(prop.value_type, ViewEntity) and prop.value_type not in existing_views
        }
        for new_value_type in new_value_types:
            if mapping_view := self._view_by_entity_id.get(new_value_type.external_id):
                new_rules.views.append(mapping_view)
            else:
                warnings.warn(NeatValueWarning(f"View {new_value_type} not found in mapping"), stacklevel=2)

        # Add missing enums
        existing_enum_collections = {item.collection for item in new_rules.enum or []}
        new_enums = {
            prop.value_type.collection
            for prop in new_rules.properties
            if isinstance(prop.value_type, Enum) and prop.value_type.collection not in existing_enum_collections
        }
        if new_enums:
            new_rules.enum = new_rules.enum or SheetList[DMSEnum]([])
            for item in self.mapping.enum or []:
                if item.collection in new_enums:
                    new_rules.enum.append(item)

        return JustRules(new_rules)

    def _find_overwrites(self, prop: DMSProperty, mapping_prop: DMSProperty) -> tuple[dict[str, Any], list[str]]:
        """Finds the properties that need to be overwritten and returns them.

        In addition, conflicting properties are returned. Note that overwriting properties that are
        originally None is not considered a conflict. Thus, you can have properties to overwrite but no
        conflicts.

        Args:
            prop: The property to compare.
            mapping_prop: The property to compare against.

        Returns:
            A tuple with the properties to overwrite and the conflicting properties.

        """
        to_overwrite: dict[str, Any] = {}
        conflicts: list[str] = []
        for field_name in self._mapping_fields:
            mapping_value = getattr(mapping_prop, field_name)
            source_value = getattr(prop, field_name)
            if mapping_value != source_value:
                to_overwrite[field_name] = mapping_value
                if source_value is not None:
                    # These are used for warnings so we use the alias to make it more readable for the user
                    conflicts.append(mapping_prop.model_fields[field_name].alias or field_name)
        return to_overwrite, conflicts


class AsParentPropertyId(RulesTransformer[DMSRules, DMSRules]):
    """Looks up all view properties that map to the same container property,
    and changes the child view property id to match the parent property id.
    """

    def __init__(self, client: NeatClient | None = None) -> None:
        self._client = client

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        input_rules = self._to_rules(rules)
        new_rules = input_rules.model_copy(deep=True)
        new_rules.metadata.version += "_as_parent_name"

        path_by_view = self._inheritance_path_by_view(new_rules)
        view_by_container_property = self._view_by_container_properties(new_rules)

        parent_view_property_by_container_property = self._get_parent_view_property_by_container_property(
            path_by_view, view_by_container_property
        )

        for prop in new_rules.properties:
            if prop.container and prop.container_property:
                if parent_name := parent_view_property_by_container_property.get(
                    (prop.container, prop.container_property)
                ):
                    prop.view_property = parent_name

        return JustRules(new_rules)

    # Todo: Move into Probe class. Note this means that the Probe class must take a NeatClient as an argument.
    def _inheritance_path_by_view(self, rules: DMSRules) -> dict[ViewEntity, list[ViewEntity]]:
        parents_by_view: dict[ViewEntity, list[ViewEntity]] = {view.view: view.implements or [] for view in rules.views}

        path_by_view: dict[ViewEntity, list[ViewEntity]] = {}
        for view in rules.views:
            path_by_view[view.view] = self._get_inheritance_path(
                view.view, parents_by_view, rules.metadata.as_data_model_id()
            )
        return path_by_view

    def _get_inheritance_path(
        self, view: ViewEntity, parents_by_view: dict[ViewEntity, list[ViewEntity]], data_model_id: dm.DataModelId
    ) -> list[ViewEntity]:
        if parents_by_view.get(view) == []:
            # We found the root.
            return [view]
        if view not in parents_by_view and self._client is not None:
            # Lookup the parent
            view_id = view.as_id()
            read_views = self._client.loaders.views.retrieve([view_id])
            if not read_views:
                # Warning? Should be caught by validation
                raise ResourceNotFoundError(view_id, "view", data_model_id, "data model")
            parent_view_latest = max(read_views, key=lambda view: view.created_time)
            parents_by_view[ViewEntity.from_id(parent_view_latest.as_id())] = [
                ViewEntity.from_id(grand_parent) for grand_parent in parent_view_latest.implements or []
            ]
        elif view not in parents_by_view:
            raise CDFMissingClientError(
                f"The data model {data_model_id} is referencing a view that is not in the data model."
                f"Please provide a client to lookup the view."
            )

        inheritance_path = [view]
        seen = {view}
        if view in parents_by_view:
            for parent in parents_by_view[view]:
                parent_path = self._get_inheritance_path(parent, parents_by_view, data_model_id)
                inheritance_path.extend([p for p in parent_path if p not in seen])
                seen.update(parent_path)
        return inheritance_path

    def _view_by_container_properties(
        self, rules: DMSRules
    ) -> dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]]:
        view_properties_by_container_properties: dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]] = (
            defaultdict(list)
        )
        view_with_properties: set[ViewEntity] = set()
        for prop in rules.properties:
            if not prop.container or not prop.container_property:
                continue
            view_properties_by_container_properties[(prop.container, prop.container_property)].append(
                (prop.view, prop.view_property)
            )
            view_with_properties.add(prop.view)

        # We need to look up all parent properties.
        to_lookup = {view.view.as_id() for view in rules.views if view.view not in view_with_properties}
        if to_lookup and self._client is None:
            raise CDFMissingClientError(
                f"Views {to_lookup} are not in the data model. Please provide a client to lookup the views."
            )
        elif to_lookup and self._client:
            read_views = self._client.loaders.views.retrieve(list(to_lookup), include_ancestor=True)
            write_views = [self._client.loaders.views.as_write(read_view) for read_view in read_views]
            # We use the write/request format of the views as the read/response format contains all properties
            # including ancestor properties. The goal is to find the property name used in the parent
            # and thus we cannot have that repeated in the child views.
            for write_view in write_views:
                view_id = write_view.as_id()
                view_entity = ViewEntity.from_id(view_id)

                for property_id, property_ in (write_view.properties or {}).items():
                    if not isinstance(property_, dm.MappedPropertyApply):
                        continue
                    container_entity = ContainerEntity.from_id(property_.container)
                    view_properties_by_container_properties[
                        (container_entity, property_.container_property_identifier)
                    ].append((view_entity, property_id))

        return view_properties_by_container_properties

    @staticmethod
    def _get_parent_view_property_by_container_property(
        path_by_view, view_by_container_properties: dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]]
    ) -> dict[tuple[ContainerEntity, str], str]:
        parent_name_by_container_property: dict[tuple[ContainerEntity, str], str] = {}
        for (container, container_property), view_properties in view_by_container_properties.items():
            if len(view_properties) == 1:
                continue
            # Shortest path is the parent
            _, prop_name = min(view_properties, key=lambda prop: len(path_by_view[prop[0]]))
            parent_name_by_container_property[(container, container_property)] = prop_name
        return parent_name_by_container_property
