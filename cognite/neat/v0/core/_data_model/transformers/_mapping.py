import warnings
from abc import ABC
from collections import defaultdict
from typing import Any, ClassVar, Literal

from cognite.client import data_modeling as dm

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._data_model.models import PhysicalDataModel, SheetList
from cognite.neat.v0.core._data_model.models.data_types import Enum
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    ContainerEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.physical import (
    PhysicalContainer,
    PhysicalEnum,
    PhysicalProperty,
)
from cognite.neat.v0.core._issues.errors import (
    CDFMissingClientError,
    NeatValueError,
    ResourceNotFoundError,
)
from cognite.neat.v0.core._issues.warnings import PropertyOverwritingWarning

from ._base import VerifiedDataModelTransformer


class MapOntoTransformers(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel], ABC):
    """Base class for transformers that map one data model onto another."""

    ...


class MapOneToOne(MapOntoTransformers):
    """Takes transform data models and makes it into an extension of the reference data model.

    Note this transformer mutates the input data model.

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
        self,
        reference: PhysicalDataModel,
        view_extension_mapping: dict[str, str],
        default_extension: str | None = None,
    ) -> None:
        self.reference = reference
        self.view_extension_mapping = view_extension_mapping
        self.default_extension = default_extension

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        solution: PhysicalDataModel = data_model
        view_by_external_id = {view.view.external_id: view for view in solution.views}
        ref_view_by_external_id = {view.view.external_id: view for view in self.reference.views}

        if invalid_views := set(self.view_extension_mapping.keys()) - set(view_by_external_id.keys()):
            raise ValueError(f"Views are not in this dat model {invalid_views}")
        if invalid_views := set(self.view_extension_mapping.values()) - set(ref_view_by_external_id.keys()):
            raise ValueError(f"Views are not in the reference data model {invalid_views}")
        if self.default_extension and self.default_extension not in ref_view_by_external_id:
            raise ValueError(f"Default extension view not in the reference data model {self.default_extension}")

        properties_by_view_external_id: dict[str, dict[str, PhysicalProperty]] = defaultdict(dict)
        for prop in solution.properties:
            properties_by_view_external_id[prop.view.external_id][prop.view_property] = prop

        ref_properties_by_view_external_id: dict[str, dict[str, PhysicalProperty]] = defaultdict(dict)
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

        return solution


class PhysicalDataModelMapper(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    """Maps properties and classes using the given mapping.

    Args:
        mapping: The mapping to use represented as a physical data model object.
        data_type_conflict: How to handle data type conflicts. The default is "overwrite".
            A data type conflicts occurs when the data type of a property in the mapping is different from the
            data type of the property in the input data model. If "overwrite" the data type
            in the input data model is overwritten
            with the data type in the mapping.
    """

    _mapping_fields: ClassVar[frozenset[str]] = frozenset(
        ["connection", "value_type", "min_count", "immutable", "max_count", "default", "index", "constraint"]
    )

    def __init__(
        self,
        mapping: PhysicalDataModel,
        data_type_conflict: Literal["overwrite"] = "overwrite",
    ) -> None:
        self.mapping = mapping
        self.data_type_conflict = data_type_conflict

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        if self.data_type_conflict != "overwrite":
            raise NeatValueError(f"Invalid data_type_conflict: {self.data_type_conflict}")
        input_data_model = data_model
        new_data_model = input_data_model.model_copy(deep=True)

        views_by_external_id = {view.view.external_id: view for view in new_data_model.views}
        new_views: set[ViewEntity] = set()
        for mapping_view in self.mapping.views:
            if existing_view := views_by_external_id.get(mapping_view.view.external_id):
                existing_view.implements = mapping_view.implements
            else:
                # We need to add all the views in the mapping that are not in the input data model.
                # This is to ensure that all ValueTypes are present in the resulting data model.
                # For example, if a property is a direct relation to an Equipment view, we need to add
                # the Equipment view to the data model.
                new_data_model.views.append(mapping_view)
                new_views.add(mapping_view.view)

        properties_by_view_property = {
            (prop.view.external_id, prop.view_property): prop for prop in new_data_model.properties
        }
        existing_enum_collections = {item.collection for item in new_data_model.enum or []}
        mapping_enums_by_collection: dict[ConceptEntity, list[PhysicalEnum]] = defaultdict(list)
        for item in self.mapping.enum or []:
            mapping_enums_by_collection[item.collection].append(item)
        existing_containers = {container.container for container in new_data_model.containers or []}
        mapping_containers_by_id = {container.container: container for container in self.mapping.containers or []}
        for mapping_prop in self.mapping.properties:
            if existing_prop := properties_by_view_property.get(
                (mapping_prop.view.external_id, mapping_prop.view_property)
            ):
                to_overwrite, conflicts = self._find_overwrites(existing_prop, mapping_prop)
                if conflicts and self.data_type_conflict == "overwrite":
                    warnings.warn(
                        PropertyOverwritingWarning(
                            existing_prop.view.as_id(),
                            "view",
                            existing_prop.view_property,
                            tuple(conflicts),
                        ),
                        stacklevel=2,
                    )
                elif conflicts:
                    raise NeatValueError(
                        f"Conflicting properties for {existing_prop.view}.{existing_prop.view_property}: {conflicts}"
                    )

                for field_name, value in to_overwrite.items():
                    setattr(existing_prop, field_name, value)
                existing_prop.container = mapping_prop.container
                existing_prop.container_property = mapping_prop.container_property
            elif isinstance(mapping_prop.value_type, ViewEntity):
                # All connections must be included in the data model. This is to update the
                # ValueTypes of the implemented views.
                new_data_model.properties.append(mapping_prop)
            elif "guid" in mapping_prop.view_property.casefold():
                # All guid properties are included. Theses are necessary to get an appropriate
                # filter on the resulting view.
                new_data_model.properties.append(mapping_prop)
            else:
                # Skipping mapped properties that are not in the input data model.
                continue

            if (
                isinstance(mapping_prop.value_type, Enum)
                and mapping_prop.value_type.collection not in existing_enum_collections
            ):
                if not new_data_model.enum:
                    new_data_model.enum = SheetList[PhysicalEnum]([])
                new_data_model.enum.extend(mapping_enums_by_collection[mapping_prop.value_type.collection])

            if (
                mapping_prop.container
                and mapping_prop.container not in existing_containers
                and (new_container := mapping_containers_by_id.get(mapping_prop.container))
            ):
                # Mapping can include new containers for GUID properties
                if not new_data_model.containers:
                    new_data_model.containers = SheetList[PhysicalContainer]([])
                new_data_model.containers.append(new_container)

        return new_data_model

    def _find_overwrites(
        self, prop: PhysicalProperty, mapping_prop: PhysicalProperty
    ) -> tuple[dict[str, Any], list[str]]:
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

    @property
    def description(self) -> str:
        return f"Mapping to {self.mapping.metadata.as_data_model_id()!r}."


class AsParentPropertyId(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    """Looks up all view properties that map to the same container property,
    and changes the child view property id to match the parent property id.
    """

    def __init__(self, client: NeatClient | None = None) -> None:
        self._client = client

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        input_data_model = data_model
        new_data_model = input_data_model.model_copy(deep=True)

        path_by_view = self._inheritance_path_by_view(new_data_model)
        view_by_container_property = self._view_by_container_properties(new_data_model)

        parent_view_property_by_container_property = self._get_parent_view_property_by_container_property(
            path_by_view, view_by_container_property
        )

        for prop in new_data_model.properties:
            if prop.container and prop.container_property:
                if parent_name := parent_view_property_by_container_property.get(
                    (prop.container, prop.container_property)
                ):
                    prop.view_property = parent_name

        return new_data_model

    # Todo: Move into Probe class. Note this means that the Probe class must take a NeatClient as an argument.
    def _inheritance_path_by_view(self, data_model: PhysicalDataModel) -> dict[ViewEntity, list[ViewEntity]]:
        parents_by_view: dict[ViewEntity, list[ViewEntity]] = {
            view.view: view.implements or [] for view in data_model.views
        }

        path_by_view: dict[ViewEntity, list[ViewEntity]] = {}
        for view in data_model.views:
            path_by_view[view.view] = self._get_inheritance_path(
                view.view, parents_by_view, data_model.metadata.as_data_model_id()
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
        self, data_model: PhysicalDataModel
    ) -> dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]]:
        view_properties_by_container_properties: dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]] = (
            defaultdict(list)
        )
        view_with_properties: set[ViewEntity] = set()
        for prop in data_model.properties:
            if not prop.container or not prop.container_property:
                continue
            view_properties_by_container_properties[(prop.container, prop.container_property)].append(
                (prop.view, prop.view_property)
            )
            view_with_properties.add(prop.view)

        # We need to look up all parent properties.
        to_lookup = {view.view.as_id() for view in data_model.views if view.view not in view_with_properties}
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
        path_by_view: dict[ViewEntity, list[ViewEntity]],
        view_by_container_properties: dict[tuple[ContainerEntity, str], list[tuple[ViewEntity, str]]],
    ) -> dict[tuple[ContainerEntity, str], str]:
        parent_name_by_container_property: dict[tuple[ContainerEntity, str], str] = {}
        for (container, container_property), view_properties in view_by_container_properties.items():
            if len(view_properties) == 1:
                continue
            # Shortest path is the parent
            _, prop_name = min(view_properties, key=lambda prop: len(path_by_view[prop[0]]))
            parent_name_by_container_property[(container, container_property)] = prop_name
        return parent_name_by_container_property

    @property
    def description(self) -> str:
        return "Renaming property names to parent name"
