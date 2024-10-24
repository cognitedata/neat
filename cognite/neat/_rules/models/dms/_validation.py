from collections import defaultdict
from typing import Any, ClassVar

from cognite.client import data_modeling as dm

from cognite.neat._constants import DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat._issues import IssueList, NeatError, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import (
    PropertyDefinitionDuplicatedError,
    ResourceChangedError,
    ResourceNotDefinedError,
)
from cognite.neat._issues.warnings import (
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
)
from cognite.neat._issues.warnings.user_modeling import (
    NotNeatSupportedFilterWarning,
    ViewPropertyLimitWarning,
)
from cognite.neat._rules.models._base_rules import DataModelType, ExtensionCategory, SchemaCompleteness
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ContainerEntity, RawFilter

from ._rules import DMSProperty, DMSRules
from ._schema import DMSSchema


class DMSPostValidation:
    """This class does all the validation of the DMS rules that have dependencies between
    components."""

    # When checking for changes extension=addition, we need to check if the new view has changed.
    # For example, changing the filter is allowed, but changing the properties is not.
    changeable_view_attributes: ClassVar[set[str]] = {"filter"}

    def __init__(self, rules: DMSRules):
        self.rules = rules
        self.metadata = rules.metadata
        self.properties = rules.properties
        self.containers = rules.containers
        self.views = rules.views
        self.issue_list = IssueList()

    def validate(self) -> NeatIssueList:
        self._validate_raw_filter()
        self._consistent_container_properties()

        self._referenced_views_and_containers_are_existing_and_proper_size()
        if self.metadata.schema_ is SchemaCompleteness.extended:
            self._validate_extension()
        if self.metadata.schema_ is SchemaCompleteness.partial:
            return self.issue_list
        dms_schema = self.rules.as_schema()
        self.issue_list.extend(dms_schema.validate())
        self._validate_performance(dms_schema)
        return self.issue_list

    def _consistent_container_properties(self) -> None:
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[tuple[int, DMSProperty]]] = defaultdict(list)
        for prop_no, prop in enumerate(self.properties):
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

            # This sets the container definition for all the properties where it is not defined.
            # This allows the user to define the container only once.
            value_type = next(iter(value_types))
            list_definition = next(iter(list_definitions)) if list_definitions else None
            nullable_definition = next(iter(nullable_definitions)) if nullable_definitions else None
            default_definition = next(iter(default_definitions)) if default_definitions else None
            index_definition = next(iter(index_definitions)).split(",") if index_definitions else None
            constraint_definition = next(iter(constraint_definitions)).split(",") if constraint_definitions else None
            for _, prop in properties:
                prop.value_type = value_type
                prop.is_list = prop.is_list or list_definition
                prop.nullable = prop.nullable or nullable_definition
                prop.default = prop.default or default_definition
                prop.index = prop.index or index_definition
                prop.constraint = prop.constraint or constraint_definition
        self.issue_list.extend(errors)

    def _referenced_views_and_containers_are_existing_and_proper_size(self) -> None:
        defined_views = {view.view.as_id() for view in self.views}
        if self.metadata.schema_ is SchemaCompleteness.extended and self.rules.last:
            defined_views |= {view.view.as_id() for view in self.rules.last.views}

        property_count_by_view: dict[dm.ViewId, int] = defaultdict(int)
        errors: list[NeatIssue] = []
        for prop_no, prop in enumerate(self.properties):
            view_id = prop.view.as_id()
            if view_id not in defined_views:
                errors.append(
                    ResourceNotDefinedError[dm.ViewId](
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
        if self.metadata.schema_ is SchemaCompleteness.complete:
            defined_containers = {container.container.as_id() for container in self.containers or []}
            if self.metadata.data_model_type == DataModelType.solution and self.rules.reference:
                defined_containers |= {
                    container.container.as_id() for container in self.rules.reference.containers or []
                }

            for prop_no, prop in enumerate(self.properties):
                if prop.container and (container_id := prop.container.as_id()) not in defined_containers:
                    errors.append(
                        ResourceNotDefinedError(
                            identifier=container_id,
                            resource_type="container",
                            location="Containers Sheet",
                            column_name="Container",
                            row_number=prop_no,
                            sheet_name="Properties",
                        )
                    )
            for _container_no, container in enumerate(self.containers or []):
                for constraint_no, constraint in enumerate(container.constraint or []):
                    if constraint.as_id() not in defined_containers:
                        errors.append(
                            ResourceNotDefinedError(
                                identifier=constraint.as_id(),
                                resource_type="container",
                                location="Containers Sheet",
                                column_name="Constraint",
                                row_number=constraint_no,
                                sheet_name="Properties",
                            )
                        )
        self.issue_list.extend(errors)

    def _validate_extension(self) -> None:
        if self.metadata.schema_ is not SchemaCompleteness.extended:
            return None
        if not self.rules.last:
            raise ValueError("The schema is set to 'extended', but no last rules are provided to validate against")
        if self.metadata.extension is ExtensionCategory.rebuild:
            # Everything is allowed
            return None
        user_schema = self.rules.as_schema()
        new_containers = user_schema.containers.copy()

        last_schema = self.rules.last.as_schema()
        existing_containers = last_schema.containers.copy()

        for container_id, container in new_containers.items():
            existing_container = existing_containers.get(container_id)
            if not existing_container or existing_container == container:
                # No problem
                continue
            new_dumped = container.dump()
            existing_dumped = existing_container.dump()
            changed_attributes, changed_properties = self._changed_attributes_and_properties(
                new_dumped, existing_dumped
            )
            self.issue_list.append(
                ResourceChangedError(
                    container_id,
                    "container",
                    changed_properties=frozenset(changed_properties),
                    changed_attributes=frozenset(changed_attributes),
                )
            )

        if self.metadata.extension is ExtensionCategory.reshape:
            # Reshape allows changes to views
            return None

        new_views = user_schema.views.copy()
        existing_views = last_schema.views.copy()
        for view_id, view in new_views.items():
            existing_view = existing_views.get(view_id)
            if not existing_view or existing_view == view:
                # No problem
                continue
            changed_attributes, changed_properties = self._changed_attributes_and_properties(
                view.dump(), existing_view.dump()
            )
            existing_properties = existing_view.properties or {}
            changed_properties = [prop for prop in changed_properties if prop in existing_properties]
            changed_attributes = [attr for attr in changed_attributes if attr not in self.changeable_view_attributes]

            if not changed_attributes and not changed_properties:
                # Only added new properties, no problem
                continue
            self.issue_list.append(
                ResourceChangedError(
                    view_id,
                    "view",
                    changed_properties=frozenset(changed_properties),
                    changed_attributes=frozenset(changed_attributes),
                )
            )

    def _validate_performance(self, dms_schema: DMSSchema) -> None:
        for view_id, view in dms_schema.views.items():
            mapped_containers = dms_schema._get_mapped_container_from_view(view_id)

            if mapped_containers and len(mapped_containers) > 10:
                self.issue_list.append(
                    NotSupportedViewContainerLimitWarning(
                        view_id,
                        len(mapped_containers),
                    )
                )
                if (
                    view.filter
                    and isinstance(view.filter, dm.filters.HasData)
                    and len(view.filter.dump()["hasData"]) > 10
                ):
                    self.issue_list.append(
                        NotSupportedHasDataFilterLimitWarning(
                            view_id,
                            len(view.filter.dump()["hasData"]),
                        )
                    )

    def _validate_raw_filter(self) -> None:
        for view in self.views:
            if view.filter_ and isinstance(view.filter_, RawFilter):
                self.issue_list.append(
                    NotNeatSupportedFilterWarning(view.view.as_id()),
                )

    @staticmethod
    def _changed_attributes_and_properties(
        new_dumped: dict[str, Any], existing_dumped: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Helper method to find the changed attributes and properties between two containers or views."""
        new_attributes = {key: value for key, value in new_dumped.items() if key != "properties"}
        existing_attributes = {key: value for key, value in existing_dumped.items() if key != "properties"}
        changed_attributes = [key for key in new_attributes if new_attributes[key] != existing_attributes.get(key)]
        new_properties = new_dumped.get("properties", {})
        existing_properties = existing_dumped.get("properties", {})
        changed_properties = [prop for prop in new_properties if new_properties[prop] != existing_properties.get(prop)]
        return changed_attributes, changed_properties
