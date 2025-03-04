import warnings
from collections import Counter, defaultdict
from collections.abc import Mapping
from functools import lru_cache

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerList, ViewId, ViewList
from cognite.client.data_classes.data_modeling.views import (
    ReverseDirectRelation,
    ReverseDirectRelationApply,
    ViewProperty,
    ViewPropertyApply,
)

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes.data_modeling import ViewApplyDict
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._constants import (
    COGNITE_MODELS,
    COGNITE_SPACES,
    DMS_CONTAINER_PROPERTY_SIZE_LIMIT,
    DMS_VIEW_CONTAINER_SIZE_LIMIT,
)
from cognite.neat._issues import IssueList, NeatError
from cognite.neat._issues.errors import (
    CDFMissingClientError,
    PropertyDefinitionDuplicatedError,
    PropertyMappingDuplicatedError,
    PropertyNotFoundError,
    ResourceDuplicatedError,
    ResourceNotFoundError,
    ReversedConnectionNotFeasibleError,
)
from cognite.neat._issues.errors._external import CDFMissingResourcesError
from cognite.neat._issues.warnings import (
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
    UndefinedViewWarning,
    user_modeling,
)
from cognite.neat._issues.warnings.user_modeling import (
    ContainerPropertyLimitWarning,
    DirectRelationMissingSourceWarning,
    NotNeatSupportedFilterWarning,
)
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ContainerEntity, RawFilter
from cognite.neat._rules.models.entities._single_value import (
    ViewEntity,
)
from cognite.neat._utils.spreadsheet import SpreadsheetRead
from cognite.neat._utils.text import humanize_collection

from ._rules import DMSProperty, DMSRules


class DMSValidation:
    """This class does all the validation of the DMS rules that have dependencies between
    components."""

    def __init__(
        self,
        rules: DMSRules,
        client: NeatClient | None = None,
        read_info_by_spreadsheet: dict[str, SpreadsheetRead] | None = None,
    ) -> None:
        self._rules = rules
        self._client = client
        self._metadata = rules.metadata
        self._properties = rules.properties
        self._containers = rules.containers
        self._views = rules.views
        self._read_info_by_spreadsheet = read_info_by_spreadsheet or {}

    def imported_views_and_containers_ids(
        self, include_views_with_no_properties: bool = True
    ) -> tuple[set[ViewEntity], set[ContainerEntity]]:
        existing_views = {view.view for view in self._views}
        imported_views: set[ViewEntity] = set()
        for view in self._views:
            for parent in view.implements or []:
                if parent not in existing_views:
                    imported_views.add(parent)
        existing_containers = {container.container for container in self._containers or []}
        imported_containers: set[ContainerEntity] = set()
        view_with_properties: set[ViewEntity] = set()
        for prop in self._properties:
            if prop.container and prop.container not in existing_containers:
                imported_containers.add(prop.container)
            if prop.view not in existing_views:
                imported_views.add(prop.view)
            view_with_properties.add(prop.view)

        for container in self._containers or []:
            for required in container.constraint or []:
                if required not in existing_containers:
                    imported_containers.add(required)

        if include_views_with_no_properties:
            extra_views = existing_views - view_with_properties
            imported_views.update({view for view in extra_views})

        return imported_views, imported_containers

    def validate(self) -> IssueList:
        imported_views, imported_containers = self.imported_views_and_containers_ids(
            include_views_with_no_properties=False
        )
        if (imported_views or imported_containers) and self._client is None:
            raise CDFMissingClientError(
                f"{self._rules.metadata.as_data_model_id()} has imported views and/or container: "
                f"{imported_views}, {imported_containers}."
            )
        referenced_views = ViewList([])
        referenced_containers = ContainerList([])
        if self._client:
            referenced_views = self._client.loaders.views.retrieve(
                list(imported_views), include_connected=True, include_ancestor=True
            )
            referenced_containers = self._client.loaders.containers.retrieve(
                list(imported_containers), include_connected=True
            )

            missing_views = {view.as_id() for view in imported_views} - {view.as_id() for view in referenced_views}
            missing_containers = {container.as_id() for container in imported_containers} - {
                container.as_id() for container in referenced_containers
            }

            if missing_views or missing_containers:
                raise CDFMissingResourcesError(resources=f"{missing_views.union(missing_containers)}")

        # Setup data structures for validation
        dms_schema = self._rules.as_schema()
        ref_view_by_id = {view.as_id(): view for view in referenced_views}
        ref_container_by_id = {container.as_id(): container for container in referenced_containers}
        # All containers and views are the Containers/Views in the DMSRules + the referenced ones
        all_containers_by_id: dict[dm.ContainerId, dm.ContainerApply | dm.Container] = {
            **dict(dms_schema.containers.items()),
            **ref_container_by_id,
        }
        all_views_by_id: dict[dm.ViewId, dm.ViewApply | dm.View] = {**dict(dms_schema.views.items()), **ref_view_by_id}
        properties_by_ids = self._as_properties_by_ids(dms_schema.views, ref_view_by_id)
        ref_properties_by_ids = self._as_properties_by_ids(ref_view_by_id, {})
        all_properties_by_ids = {**ref_properties_by_ids, **properties_by_ids}
        view_properties_by_id = self._as_view_properties_by_id(properties_by_ids)
        parents_view_ids_by_child_id = self._parent_view_ids_by_child_id(all_views_by_id)

        issue_list = IssueList()

        # Validated for duplicated resource
        issue_list.extend(self._duplicated_resources())

        # Neat DMS classes Validation
        # These are errors that can only happen due to the format of the Neat DMS classes
        issue_list.extend(self._validate_raw_filter())
        issue_list.extend(self._consistent_container_properties())
        issue_list.extend(self._validate_value_type_existence())
        issue_list.extend(
            self._validate_property_referenced_views_and_containers_exists(all_views_by_id, all_containers_by_id)
        )

        # SDK classes validation
        issue_list.extend(self._containers_are_proper_size(dms_schema))
        issue_list.extend(
            self._validate_reverse_connections(
                properties_by_ids, all_containers_by_id, parents_view_ids_by_child_id, all_properties_by_ids
            )
        )
        issue_list.extend(self._validate_schema(dms_schema, all_views_by_id, all_containers_by_id))
        issue_list.extend(self._validate_referenced_container_limits(dms_schema.views, view_properties_by_id))
        issue_list.extend(self._same_space_views_and_data_model())
        return issue_list

    def _same_space_views_and_data_model(self) -> IssueList:
        issue_list = IssueList()

        schema = self._rules.as_schema(remove_cdf_spaces=True)

        if schema.data_model and schema.views:
            data_model_space = schema.data_model.space
            views_spaces = {view.space for view in schema.views.values()}

            if data_model_space not in views_spaces:
                issue_list.append(
                    user_modeling.ViewsAndDataModelNotInSameSpaceWarning(
                        data_model_space=data_model_space,
                        views_spaces=humanize_collection(views_spaces),
                    )
                )

        return issue_list

    def _duplicated_resources(self) -> IssueList:
        issue_list = IssueList()

        properties_sheet = self._read_info_by_spreadsheet.get("Properties")
        views_sheet = self._read_info_by_spreadsheet.get("Views")
        containers_sheet = self._read_info_by_spreadsheet.get("Containers")

        visited = defaultdict(list)
        for row_no, property_ in enumerate(self._properties):
            visited[property_._identifier()].append(
                properties_sheet.adjusted_row_number(row_no) if properties_sheet else row_no + 1
            )

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            issue_list.append(
                ResourceDuplicatedError(
                    identifier[1],
                    "property",
                    (
                        f"the Properties sheet at row {humanize_collection(rows)} "
                        "if data model is read from a spreadsheet."
                    ),
                )
            )

        visited = defaultdict(list)
        for row_no, view in enumerate(self._views):
            visited[view._identifier()].append(views_sheet.adjusted_row_number(row_no) if views_sheet else row_no + 1)

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            issue_list.append(
                ResourceDuplicatedError(
                    identifier[0],
                    "view",
                    (f"the Views sheet at row {humanize_collection(rows)} if data model is read from a spreadsheet."),
                )
            )

        if self._containers:
            visited = defaultdict(list)
            for row_no, container in enumerate(self._containers):
                visited[container._identifier()].append(
                    containers_sheet.adjusted_row_number(row_no) if containers_sheet else row_no + 1
                )

            for identifier, rows in visited.items():
                if len(rows) == 1:
                    continue
                issue_list.append(
                    ResourceDuplicatedError(
                        identifier[0],
                        "container",
                        (
                            f"the Containers sheet at row {humanize_collection(rows)} "
                            "if data model is read from a spreadsheet."
                        ),
                    )
                )

        return issue_list

    @staticmethod
    def _as_properties_by_ids(
        view_by_id: Mapping[dm.ViewId, dm.ViewApply] | Mapping[dm.ViewId, dm.View],
        ref_view_by_id: dict[dm.ViewId, dm.View],
    ) -> dict[tuple[ViewId, str], ViewPropertyApply | ViewProperty]:
        # Priority DMS schema properties.
        # No need to do long lookups in ref_views as these already contain all ancestor properties.
        properties_by_id: dict[tuple[ViewId, str], ViewPropertyApply | ViewProperty] = {}
        for view_id, view in view_by_id.items():
            for prop_id, prop in (view.properties or {}).items():
                properties_by_id[(view_id, prop_id)] = prop
            if view.implements:
                to_check = view.implements.copy()
                while to_check:
                    parent_id = to_check.pop()
                    if parent_id in view_by_id:
                        # Priority of the DMS schema properties
                        parent_view = view_by_id[parent_id]
                        for prop_id, prop in (parent_view.properties or {}).items():
                            if (view_id, prop_id) not in properties_by_id:
                                properties_by_id[(view_id, prop_id)] = prop
                        to_check.extend(parent_view.implements or [])
                    elif parent_id in ref_view_by_id:
                        # SDK properties
                        parent_read_view = ref_view_by_id[parent_id]
                        for prop_id, read_prop in parent_read_view.properties.items():
                            if (view_id, prop_id) not in properties_by_id:
                                properties_by_id[(view_id, prop_id)] = read_prop
                        # Read format of views already includes all ancestor properties
                        # so no need to check further
                    else:
                        # Missing views are caught else where
                        continue

        return properties_by_id

    @staticmethod
    def _as_view_properties_by_id(
        properties_by_ids: dict[tuple[ViewId, str], ViewPropertyApply | ViewProperty],
    ) -> dict[ViewId, list[tuple[str, ViewProperty | ViewPropertyApply]]]:
        view_properties_by_id: dict[dm.ViewId, list[tuple[str, ViewProperty | ViewPropertyApply]]] = defaultdict(list)
        for (view_id, prop_id), prop in properties_by_ids.items():
            view_properties_by_id[view_id].append((prop_id, prop))
        return view_properties_by_id

    @staticmethod
    def _parent_view_ids_by_child_id(
        all_views_by_id: dict[dm.ViewId, dm.ViewApply | dm.View],
    ) -> dict[ViewId, set[ViewId]]:
        @lru_cache
        def get_parents(child_view_id: ViewId) -> set[ViewId]:
            if child_view_id not in all_views_by_id:
                return set()
            child_view = all_views_by_id[child_view_id]
            parents = set(child_view.implements or [])
            for parent_id in child_view.implements or []:
                parents.update(get_parents(parent_id))
            return parents

        parents_by_view: dict[dm.ViewId, set[dm.ViewId]] = {}
        for view_id in all_views_by_id:
            parents_by_view[view_id] = get_parents(view_id)
        return parents_by_view

    def _consistent_container_properties(self) -> IssueList:
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[tuple[int, DMSProperty]]] = defaultdict(list)
        for prop_no, prop in enumerate(self._properties):
            if prop.container and prop.container_property:
                container_properties_by_id[(prop.container, prop.container_property)].append((prop_no, prop))
        properties_sheet = self._read_info_by_spreadsheet.get("Properties")
        errors = IssueList()
        for (container, prop_name), properties in container_properties_by_id.items():
            if len(properties) == 1:
                continue
            container_id = container.as_id()

            row_numbers = {prop_no for prop_no, _ in properties}
            if properties_sheet:
                row_numbers = {properties_sheet.adjusted_row_number(row_no) for row_no in row_numbers}
            value_types = {prop.value_type for _, prop in properties if prop.value_type}
            # The container type 'direct' is an exception. On a container the type direct can point to any
            # node. The value type is typically set on the view.
            is_all_direct = all(prop.connection == "direct" for _, prop in properties)
            if len(value_types) > 1 and not is_all_direct:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset({v.dms._type if isinstance(v, DataType) else str(v) for v in value_types}),
                        tuple(row_numbers),
                        "rows",
                    )
                )
            list_definitions = {prop.is_list for _, prop in properties if prop.is_list is not None}
            if len(list_definitions) > 1:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset(list_definitions),
                        tuple(row_numbers),
                        "rows",
                    )
                )
            nullable_definitions = {prop.nullable for _, prop in properties if prop.nullable is not None}
            if len(nullable_definitions) > 1:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset(nullable_definitions),
                        tuple(row_numbers),
                        "rows",
                    )
                )
            default_definitions = {prop.default for _, prop in properties if prop.default is not None}
            if len(default_definitions) > 1:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset(
                            tuple(f"{k}:{v}" for k, v in def_.items()) if isinstance(def_, dict) else def_
                            for def_ in default_definitions
                        ),
                        tuple(row_numbers),
                        "rows",
                    )
                )
            index_definitions = {",".join(prop.index) for _, prop in properties if prop.index is not None}
            if len(index_definitions) > 1:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset(index_definitions),
                        tuple(row_numbers),
                        "rows",
                    )
                )
            constraint_definitions = {
                ",".join(prop.constraint) for _, prop in properties if prop.constraint is not None
            }
            if len(constraint_definitions) > 1:
                errors.append(
                    PropertyDefinitionDuplicatedError[dm.ContainerId](
                        container_id,
                        "container",
                        prop_name,
                        frozenset(constraint_definitions),
                        tuple(row_numbers),
                        "rows",
                    )
                )

        return errors

    @staticmethod
    def _containers_are_proper_size(dms_schema: DMSSchema) -> IssueList:
        errors = IssueList()
        for container_id, container in dms_schema.containers.items():
            count = len(container.properties or {})
            if count > DMS_CONTAINER_PROPERTY_SIZE_LIMIT:
                errors.append(ContainerPropertyLimitWarning(container_id, count))

        return errors

    @staticmethod
    def _validate_referenced_container_limits(
        views: ViewApplyDict, view_properties_by_id: dict[dm.ViewId, list[tuple[str, ViewProperty | ViewPropertyApply]]]
    ) -> IssueList:
        issue_list = IssueList()
        for view_id, view in views.items():
            view_properties = view_properties_by_id.get(view_id, [])
            mapped_containers = {
                prop.container
                for _, prop in view_properties
                if isinstance(prop, dm.MappedPropertyApply | dm.MappedProperty)
            }

            if mapped_containers and len(mapped_containers) > DMS_VIEW_CONTAINER_SIZE_LIMIT:
                issue_list.append(
                    NotSupportedViewContainerLimitWarning(
                        view_id,
                        len(mapped_containers),
                    )
                )

            if view.filter and isinstance(view.filter, dm.filters.HasData) and len(view.filter.dump()["hasData"]) > 10:
                issue_list.append(
                    NotSupportedHasDataFilterLimitWarning(
                        view_id,
                        len(view.filter.dump()["hasData"]),
                    )
                )
        return issue_list

    def _validate_raw_filter(self) -> IssueList:
        issue_list = IssueList()
        for view in self._views:
            if view.filter_ and isinstance(view.filter_, RawFilter) and view.view.space not in COGNITE_SPACES:
                issue_list.append(
                    NotNeatSupportedFilterWarning(view.view.as_id()),
                )
        return issue_list

    def _validate_value_type_existence(self) -> IssueList:
        views = {prop_.view for prop_ in self._properties}.union({view_.view for view_ in self._views})
        issue_list = IssueList()
        for prop_ in self._properties:
            if isinstance(prop_.value_type, ViewEntity) and prop_.value_type not in views:
                issue_list.append(
                    UndefinedViewWarning(
                        str(prop_.view),
                        str(prop_.value_type),
                        prop_.view_property,
                    )
                )
        return issue_list

    def _validate_property_referenced_views_and_containers_exists(
        self,
        view_by_id: dict[dm.ViewId, dm.ViewApply | dm.View],
        containers_by_id: dict[dm.ContainerId, dm.ContainerApply | dm.Container],
    ) -> IssueList:
        issue_list = IssueList()
        for prop in self._properties:
            if prop.container:
                container_id = prop.container.as_id()
                if container_id not in containers_by_id:
                    issue_list.append(
                        ResourceNotFoundError(
                            container_id,
                            "container",
                            prop.view,
                            "view",
                        )
                    )
                elif (
                    prop.container_property and prop.container_property not in containers_by_id[container_id].properties
                ):
                    issue_list.append(
                        PropertyNotFoundError(
                            prop.container,
                            "container property",
                            prop.container_property,
                            dm.PropertyId(prop.view.as_id(), prop.view_property),
                            "view property",
                        )
                    )

            if prop.view.as_id() not in view_by_id:
                issue_list.append(
                    ResourceNotFoundError(
                        prop.view,
                        "view",
                        prop.view_property,
                        "property",
                    )
                )

        return issue_list

    def _validate_reverse_connections(
        self,
        view_property_by_property_id: dict[tuple[dm.ViewId, str], ViewPropertyApply | ViewProperty],
        containers_by_id: dict[dm.ContainerId, dm.ContainerApply | dm.Container],
        parents_by_view: dict[dm.ViewId, set[dm.ViewId]],
        all_view_property_by_property_id: dict[tuple[dm.ViewId, str], ViewPropertyApply | ViewProperty],
    ) -> IssueList:
        issue_list = IssueList()
        # do not check for reverse connections in Cognite models
        if self._metadata.as_data_model_id() in COGNITE_MODELS:
            return issue_list

        for (view_id, prop_id), prop_ in view_property_by_property_id.items():
            if not isinstance(prop_, ReverseDirectRelationApply | ReverseDirectRelation):
                continue
            target_id = prop_.through.source, prop_.through.property
            if target_id not in all_view_property_by_property_id:
                issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        view_id,
                        "reversed connection",
                        prop_id,
                        f"The {prop_.through.source} {prop_.through.property} does not exist",
                    )
                )
                continue
            if isinstance(target_id[0], dm.ContainerId):
                # Todo: How to handle this case? Should not happen if you created the model with Neat
                continue

            target_property = all_view_property_by_property_id[(target_id[0], target_id[1])]
            # Validate that the target is a direct relation pointing to the view_id
            is_direct_relation = False
            if isinstance(target_property, dm.MappedProperty) and isinstance(target_property.type, dm.DirectRelation):
                is_direct_relation = True
            elif isinstance(target_property, dm.MappedPropertyApply):
                container = containers_by_id[target_property.container]
                if target_property.container_property_identifier in container.properties:
                    container_property = container.properties[target_property.container_property_identifier]
                    if isinstance(container_property.type, dm.DirectRelation):
                        is_direct_relation = True
            if not is_direct_relation:
                issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        view_id,
                        "reversed connection",
                        prop_id,
                        f"{prop_.through.source} {prop_.through.property} is not a direct relation",
                    )
                )
                continue
            if not (
                isinstance(target_property, dm.MappedPropertyApply | dm.MappedProperty)
                # The direct relation is pointing to the view_id or one of its parents
                and (target_property.source == view_id or target_property.source in parents_by_view[view_id])
            ):
                issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        view_id,
                        "reversed connection",
                        prop_id,
                        f"{prop_.through.source} {prop_.through.property} is not pointing to {view_id}",
                    )
                )
        return issue_list

    @staticmethod
    def _validate_schema(
        schema: DMSSchema,
        view_by_id: dict[dm.ViewId, dm.ViewApply | dm.View],
        containers_by_id: dict[dm.ContainerId, dm.ContainerApply | dm.Container],
    ) -> IssueList:
        errors: set[NeatError] = set()
        defined_spaces = schema.spaces.copy()

        for container_id, container in schema.containers.items():
            if container.space not in defined_spaces:
                errors.add(ResourceNotFoundError(container.space, "space", container_id, "container"))
            for constraint in container.constraints.values():
                if isinstance(constraint, dm.RequiresConstraint) and constraint.require not in containers_by_id:
                    errors.add(ResourceNotFoundError(constraint.require, "container", container_id, "container"))

        for view_id, view in schema.views.items():
            if view.space not in defined_spaces:
                errors.add(ResourceNotFoundError(view.space, "space", view_id, "view"))

            for parent in view.implements or []:
                if parent not in view_by_id:
                    errors.add(PropertyNotFoundError(parent, "view", "implements", view_id, "view"))

            for prop_name, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    ref_container = containers_by_id.get(prop.container)
                    if ref_container is None:
                        errors.add(ResourceNotFoundError(prop.container, "container", view_id, "view"))
                    elif prop.container_property_identifier not in ref_container.properties:
                        errors.add(
                            PropertyNotFoundError(
                                prop.container,
                                "container",
                                prop.container_property_identifier,
                                view_id,
                                "view",
                            )
                        )
                    else:
                        container_property = ref_container.properties[prop.container_property_identifier]

                        if isinstance(container_property.type, dm.DirectRelation) and prop.source is None:
                            warnings.warn(
                                DirectRelationMissingSourceWarning(view_id, prop_name),
                                stacklevel=2,
                            )

                if (
                    isinstance(prop, dm.EdgeConnectionApply | ReverseDirectRelationApply)
                    and prop.source not in view_by_id
                ):
                    errors.add(PropertyNotFoundError(prop.source, "view", prop_name, view_id, "view"))

                if (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in view_by_id
                ):
                    errors.add(PropertyNotFoundError(prop.edge_source, "view", prop_name, view_id, "view"))

            # This allows for multiple view properties to be mapped to the same container property,
            # as long as they have different external_id, otherwise this will lead to raising
            # error ContainerPropertyUsedMultipleTimesError
            property_count = Counter(
                (prop.container, prop.container_property_identifier, view_property_identifier)
                for view_property_identifier, prop in (view.properties or {}).items()
                if isinstance(prop, dm.MappedPropertyApply)
            )

            for (
                container_id,
                container_property_identifier,
                _,
            ), count in property_count.items():
                if count > 1:
                    view_properties = [
                        prop_name
                        for prop_name, prop in (view.properties or {}).items()
                        if isinstance(prop, dm.MappedPropertyApply)
                        and (prop.container, prop.container_property_identifier)
                        == (container_id, container_property_identifier)
                    ]
                    errors.add(
                        PropertyMappingDuplicatedError(
                            container_id,
                            "container",
                            container_property_identifier,
                            frozenset({dm.PropertyId(view_id, prop_name) for prop_name in view_properties}),
                            "view property",
                        )
                    )

        if schema.data_model:
            model = schema.data_model
            if model.space not in defined_spaces:
                errors.add(ResourceNotFoundError(model.space, "space", model.as_id(), "data model"))

            view_counts: dict[dm.ViewId, int] = defaultdict(int)
            for view_id_or_class in model.views or []:
                view_id = view_id_or_class if isinstance(view_id_or_class, dm.ViewId) else view_id_or_class.as_id()
                if view_id not in view_by_id:
                    errors.add(ResourceNotFoundError(view_id, "view", model.as_id(), "data model"))
                view_counts[view_id] += 1

            for view_id, count in view_counts.items():
                if count > 1:
                    errors.add(
                        ResourceDuplicatedError(
                            view_id,
                            "view",
                            f"DMS {model.as_id()!r}",
                        )
                    )

        return IssueList(list(errors))
