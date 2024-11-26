import warnings
from collections import Counter, defaultdict
from typing import ClassVar, cast

from cognite.client import data_modeling as dm

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, ViewApplyDict
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._constants import COGNITE_MODELS, DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat._issues import IssueList, NeatError, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import (
    CDFMissingClientError,
    PropertyDefinitionDuplicatedError,
    PropertyMappingDuplicatedError,
    PropertyNotFoundError,
    ResourceDuplicatedError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
    ReversedConnectionNotFeasibleError,
)
from cognite.neat._issues.warnings import (
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
    UndefinedViewWarning,
)
from cognite.neat._issues.warnings.user_modeling import (
    DirectRelationMissingSourceWarning,
    NotNeatSupportedFilterWarning,
    ViewPropertyLimitWarning,
)
from cognite.neat._rules.analysis import DMSAnalysis
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ContainerEntity, RawFilter
from cognite.neat._rules.models.entities._single_value import (
    ReverseConnectionEntity,
    ViewEntity,
)
from cognite.neat._utils.rdf_ import get_inheritance_path

from ._rules import DMSProperty, DMSRules


class DMSValidation:
    """This class does all the validation of the DMS rules that have dependencies between
    components."""

    # When checking for changes extension=addition, we need to check if the new view has changed.
    # For example, changing the filter is allowed, but changing the properties is not.
    changeable_view_attributes: ClassVar[set[str]] = {"filter"}

    def __init__(self, rules: DMSRules, client: NeatClient | None = None) -> None:
        self._rules = rules
        self._client = client
        self._metadata = rules.metadata
        self._properties = rules.properties
        self._containers = rules.containers
        self._views = rules.views
        self._issue_list = IssueList()
        self._probe = DMSAnalysis(rules)
        self._all_properties_by_ids: dict[tuple[ViewEntity, str], DMSProperty] = {}

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

        if include_views_with_no_properties:
            extra_views = existing_views - view_with_properties
            imported_views.update({view for view in extra_views})

        return imported_views, imported_containers

    def validate(self) -> NeatIssueList:
        imported_views, imported_containers = self.imported_views_and_containers_ids()
        if (imported_views or imported_containers) and self._client is None:
            raise CDFMissingClientError(
                f"{self._rules.metadata.as_data_model_id()} has imported views and/or container."
            )
        referenced_views = ViewApplyDict()
        referenced_containers = ContainerApplyDict()
        if self._client:
            retrieved_view = self._client.loaders.views.retrieve(
                list(imported_views), include_connections=True, include_ancestor=True
            )
            referenced_views.update({view.as_id(): view for view in retrieved_view})
            retrieved_containers = self._client.loaders.containers.retrieve(
                list(imported_containers), include_connected=True
            )
            referenced_containers.update({container.as_id(): container for container in retrieved_containers})

        # Todo Need to lookup parent views.
        self._all_properties_by_ids = {
            (prop_.view, prop_.view_property): prop_
            for properties in self._probe.classes_with_properties(True, True).values()
            for prop_ in properties
        }

        self._validate_raw_filter()
        self._consistent_container_properties()
        self._validate_value_type_existence()
        self._validate_reverse_connections()
        self._referenced_views_and_containers_are_existing_and_proper_size()

        dms_schema = self._rules.as_schema()
        self._validate_schema(dms_schema)

        self._validate_referenced_container_limits(dms_schema)
        return self._issue_list

    def _consistent_container_properties(self) -> None:
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[tuple[int, DMSProperty]]] = defaultdict(list)
        for prop_no, prop in enumerate(self._properties):
            if prop.container and prop.container_property:
                container_properties_by_id[(prop.container, prop.container_property)].append((prop_no, prop))

        errors: list[NeatError] = []
        for (container, prop_name), properties in container_properties_by_id.items():
            if len(properties) == 1:
                continue
            container_id = container.as_id()
            row_numbers = {prop_no for prop_no, _ in properties}
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

        self._issue_list.extend(errors)

    def _referenced_views_and_containers_are_existing_and_proper_size(self) -> None:
        defined_views = {view.view.as_id() for view in self._views}

        property_count_by_view: dict[dm.ViewId, int] = defaultdict(int)
        errors: list[NeatIssue] = []
        for prop_no, prop in enumerate(self._properties):
            view_id = prop.view.as_id()
            if view_id not in defined_views:
                errors.append(
                    ResourceNotDefinedError(
                        identifier=view_id,
                        resource_type="view",
                        location="Views Sheet",
                        column_name="View",
                        row_number=prop_no,
                        sheet_name="Properties",
                    ),
                )
            else:
                property_count_by_view[view_id] += 1

        for view_id, count in property_count_by_view.items():
            if count > DMS_CONTAINER_PROPERTY_SIZE_LIMIT:
                errors.append(ViewPropertyLimitWarning(view_id, count))

        self._issue_list.extend(errors)

    def _get_mapped_container_from_view(self, view_id: dm.ViewId) -> set[dm.ContainerId]:
        # index all views, including ones from reference
        view_by_id = self._views.copy()
        if view_id not in view_by_id:
            raise ValueError(f"View {view_id} not found")

        indexed_implemented_views = {id_: view.implements for id_, view in view_by_id.items()}
        view_inheritance = get_inheritance_path(view_id, indexed_implemented_views)

        directly_referenced_containers = view_by_id[view_id].referenced_containers()
        inherited_referenced_containers = set()

        for parent_id in view_inheritance:
            if implemented_view := view_by_id.get(parent_id):
                inherited_referenced_containers |= implemented_view.referenced_containers()
            else:
                raise ResourceNotFoundError(parent_id, "view", view_id, "view")

        return directly_referenced_containers | inherited_referenced_containers

    def _validate_referenced_container_limits(self, dms_schema: DMSSchema) -> None:
        for view_id, view in dms_schema.views.items():
            mapped_containers = self._get_mapped_container_from_view(view_id)

            if mapped_containers and len(mapped_containers) > 10:
                self._issue_list.append(
                    NotSupportedViewContainerLimitWarning(
                        view_id,
                        len(mapped_containers),
                    )
                )

            if view.filter and isinstance(view.filter, dm.filters.HasData) and len(view.filter.dump()["hasData"]) > 10:
                self._issue_list.append(
                    NotSupportedHasDataFilterLimitWarning(
                        view_id,
                        len(view.filter.dump()["hasData"]),
                    )
                )

    def _validate_raw_filter(self) -> None:
        for view in self._views:
            if view.filter_ and isinstance(view.filter_, RawFilter):
                self._issue_list.append(
                    NotNeatSupportedFilterWarning(view.view.as_id()),
                )

    def _validate_value_type_existence(self) -> None:
        views = {prop_.view for prop_ in self._properties}.union({view_.view for view_ in self._views})

        for prop_ in self._properties:
            if isinstance(prop_.value_type, ViewEntity) and prop_.value_type not in views:
                self._issue_list.append(
                    UndefinedViewWarning(
                        str(prop_.view),
                        str(prop_.value_type),
                        prop_.view_property,
                    )
                )

    def _validate_reverse_connections(self) -> None:
        # do not check for reverse connections in Cognite models
        if self._metadata.as_data_model_id() in COGNITE_MODELS:
            return None

        for id_, prop_ in self._all_properties_by_ids.items():
            if not isinstance(prop_.connection, ReverseConnectionEntity):
                continue
            source_id = prop_.value_type, prop_.connection.property_
            if source_id not in self._all_properties_by_ids:
                self._issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        id_,
                        "reversed connection",
                        prop_.view_property,
                        str(prop_.view),
                        str(prop_.value_type),
                        prop_.connection.property_,
                    )
                )

            elif (
                source_id in self._all_properties_by_ids
                and self._all_properties_by_ids[source_id].value_type != prop_.view
            ):
                self._issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        id_,
                        "view property",
                        prop_.view_property,
                        str(prop_.view),
                        str(prop_.value_type),
                        cast(ReverseConnectionEntity, prop_.connection).property_,
                    )
                )

    def _validate_schema(self, schema: DMSSchema) -> list[NeatError]:
        errors: set[NeatError] = set()
        defined_spaces = schema.spaces.copy()
        defined_containers = schema.containers.copy()
        defined_views = schema.views.copy()

        for container in schema.containers.values():
            if container.space not in defined_spaces:
                errors.add(
                    ResourceNotFoundError[str, dm.ContainerId](container.space, "space", container.as_id(), "container")
                )

        for view in schema.views.values():
            view_id = view.as_id()
            if view.space not in defined_spaces:
                errors.add(ResourceNotFoundError(view.space, "space", view_id, "view"))

            for parent in view.implements or []:
                if parent not in defined_views:
                    errors.add(PropertyNotFoundError(parent, "view", "implements", view_id, "view"))

            for prop_name, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    ref_container = defined_containers.get(prop.container)
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

                if isinstance(prop, dm.EdgeConnectionApply) and prop.source not in defined_views:
                    errors.add(PropertyNotFoundError(prop.source, "view", prop_name, view_id, "view"))

                if (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in defined_views
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
                if view_id not in defined_views:
                    errors.add(ResourceNotFoundError(view_id, "view", model.as_id(), "data model"))
                view_counts[view_id] += 1

            for view_id, count in view_counts.items():
                if count > 1:
                    errors.add(
                        ResourceDuplicatedError(
                            view_id,
                            "view",
                            repr(model.as_id()),
                        )
                    )

        return list(errors)
