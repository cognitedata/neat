from collections import defaultdict
from typing import Any

from cognite.client import data_modeling as dm

from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._base import ExtensionCategory, SchemaCompleteness
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import ContainerEntity

from ._rules import DMSProperty, DMSRules


class DMSPostValidation:
    """This class does all the validation of the DMS rules that have dependencies between
    components."""

    def __init__(self, rules: DMSRules):
        self.rules = rules
        self.metadata = rules.metadata
        self.properties = rules.properties
        self.containers = rules.containers
        self.views = rules.views
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._consistent_container_properties()
        self._referenced_views_and_containers_are_existing()
        self._validate_extension()
        self._validate_schema()
        self._validate_performance()
        return self.issue_list

    def _consistent_container_properties(self) -> None:
        container_properties_by_id: dict[tuple[ContainerEntity, str], list[tuple[int, DMSProperty]]] = defaultdict(list)
        for prop_no, prop in enumerate(self.properties):
            if prop.container and prop.container_property:
                container_properties_by_id[(prop.container, prop.container_property)].append((prop_no, prop))

        errors: list[issues.spreadsheet.InconsistentContainerDefinitionError] = []
        for (container, prop_name), properties in container_properties_by_id.items():
            if len(properties) == 1:
                continue
            container_id = container.as_id()
            row_numbers = {prop_no for prop_no, _ in properties}
            value_types = {prop.value_type for _, prop in properties if prop.value_type}
            if len(value_types) > 1:
                errors.append(
                    issues.spreadsheet.MultiValueTypeError(
                        container_id,
                        prop_name,
                        row_numbers,
                        {v.dms._type if isinstance(v, DataType) else str(v) for v in value_types},
                    )
                )
            list_definitions = {prop.is_list for _, prop in properties if prop.is_list is not None}
            if len(list_definitions) > 1:
                errors.append(
                    issues.spreadsheet.MultiValueIsListError(container_id, prop_name, row_numbers, list_definitions)
                )
            nullable_definitions = {prop.nullable for _, prop in properties if prop.nullable is not None}
            if len(nullable_definitions) > 1:
                errors.append(
                    issues.spreadsheet.MultiNullableError(container_id, prop_name, row_numbers, nullable_definitions)
                )
            default_definitions = {prop.default for _, prop in properties if prop.default is not None}
            if len(default_definitions) > 1:
                errors.append(
                    issues.spreadsheet.MultiDefaultError(
                        container_id, prop_name, row_numbers, list(default_definitions)
                    )
                )
            index_definitions = {",".join(prop.index) for _, prop in properties if prop.index is not None}
            if len(index_definitions) > 1:
                errors.append(
                    issues.spreadsheet.MultiIndexError(container_id, prop_name, row_numbers, index_definitions)
                )
            constraint_definitions = {
                ",".join(prop.constraint) for _, prop in properties if prop.constraint is not None
            }
            if len(constraint_definitions) > 1:
                errors.append(
                    issues.spreadsheet.MultiUniqueConstraintError(
                        container_id, prop_name, row_numbers, constraint_definitions
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

    def _referenced_views_and_containers_are_existing(self) -> None:
        # There two checks are done in the same method to raise all the errors at once.
        defined_views = {view.view.as_id() for view in self.views}

        errors: list[issues.NeatValidationError] = []
        for prop_no, prop in enumerate(self.properties):
            if prop.view and (view_id := prop.view.as_id()) not in defined_views:
                errors.append(
                    issues.spreadsheet.NonExistingViewError(
                        column="View",
                        row=prop_no,
                        type="value_error.missing",
                        view_id=view_id,
                        msg="",
                        input=None,
                        url=None,
                    )
                )
        if self.metadata.schema_ is SchemaCompleteness.complete:
            defined_containers = {container.container.as_id() for container in self.containers or []}
            for prop_no, prop in enumerate(self.properties):
                if prop.container and (container_id := prop.container.as_id()) not in defined_containers:
                    errors.append(
                        issues.spreadsheet.NonExistingContainerError(
                            column="Container",
                            row=prop_no,
                            type="value_error.missing",
                            container_id=container_id,
                            msg="",
                            input=None,
                            url=None,
                        )
                    )
            for _container_no, container in enumerate(self.containers or []):
                for constraint_no, constraint in enumerate(container.constraint or []):
                    if constraint.as_id() not in defined_containers:
                        errors.append(
                            issues.spreadsheet.NonExistingContainerError(
                                column="Constraint",
                                row=constraint_no,
                                type="value_error.missing",
                                container_id=constraint.as_id(),
                                msg="",
                                input=None,
                                url=None,
                            )
                        )
        self.issue_list.extend(errors)

    def _validate_extension(self) -> None:
        if self.metadata.schema_ is not SchemaCompleteness.extended:
            return None
        if not self.rules.reference:
            raise ValueError("The schema is set to 'extended', but no reference rules are provided to validate against")
        is_solution = self.metadata.space != self.rules.reference.metadata.space
        if is_solution:
            return None
        if self.metadata.extension is ExtensionCategory.rebuild:
            # Everything is allowed
            return None
        # Is an extension of an existing model.
        user_schema = self.rules.as_schema(include_ref=False)
        ref_schema = self.rules.reference.as_schema()
        new_containers = {container.as_id(): container for container in user_schema.containers}
        existing_containers = {container.as_id(): container for container in ref_schema.containers}

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
                issues.dms.ChangingContainerError(
                    container_id=container_id,
                    changed_properties=changed_properties or None,
                    changed_attributes=changed_attributes or None,
                )
            )

        if self.metadata.extension is ExtensionCategory.reshape and self.issue_list:
            return None
        elif self.metadata.extension is ExtensionCategory.reshape:
            # Reshape allows changes to views
            return None

        new_views = {view.as_id(): view for view in user_schema.views}
        existing_views = {view.as_id(): view for view in ref_schema.views}
        for view_id, view in new_views.items():
            existing_view = existing_views.get(view_id)
            if not existing_view or existing_view == view:
                # No problem
                continue
            changed_attributes, changed_properties = self._changed_attributes_and_properties(
                view.dump(), existing_view.dump()
            )
            self.issue_list.append(
                issues.dms.ChangingViewError(
                    view_id=view_id,
                    changed_properties=changed_properties or None,
                    changed_attributes=changed_attributes or None,
                )
            )

    def _validate_performance(self) -> None:
        # we can only validate performance on complete schemas due to the need
        # to access all the container mappings
        if self.metadata.schema_ is not SchemaCompleteness.complete:
            return None

        dms_schema = self.rules.as_schema()

        for view in dms_schema.views:
            mapped_containers = dms_schema._get_mapped_container_from_view(view.as_id())

            if mapped_containers and len(mapped_containers) > 10:
                self.issue_list.append(
                    issues.dms.ViewMapsToTooManyContainersWarning(
                        view_id=view.as_id(),
                        container_ids=mapped_containers,
                    )
                )
                if (
                    view.filter
                    and isinstance(view.filter, dm.filters.HasData)
                    and len(view.filter.dump()["hasData"]) > 10
                ):
                    self.issue_list.append(
                        issues.dms.HasDataFilterAppliedToTooManyContainersWarning(
                            view_id=view.as_id(),
                            container_ids=mapped_containers,
                        )
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

    def _validate_schema(self) -> None:
        if self.metadata.schema_ is SchemaCompleteness.partial:
            return None
        elif self.metadata.schema_ is SchemaCompleteness.complete:
            rules: DMSRules = self.rules
        elif self.metadata.schema_ is SchemaCompleteness.extended:
            if not self.rules.reference:
                raise ValueError(
                    "The schema is set to 'extended', but no reference rules are provided to validate against"
                )
            # This is an extension of the reference rules, we need to merge the two
            rules = self.rules.model_copy(deep=True)
            rules.properties.extend(self.rules.reference.properties.data)
            existing_views = {view.view.as_id() for view in rules.views}
            rules.views.extend([view for view in self.rules.reference.views if view.view.as_id() not in existing_views])
            if rules.containers and self.rules.reference.containers:
                existing_containers = {container.container.as_id() for container in rules.containers.data}
                rules.containers.extend(
                    [
                        container
                        for container in self.rules.reference.containers
                        if container.container.as_id() not in existing_containers
                    ]
                )
            elif not rules.containers and self.rules.reference.containers:
                rules.containers = self.rules.reference.containers
        else:
            raise ValueError("Unknown schema completeness")

        schema = rules.as_schema()
        errors = schema.validate()
        self.issue_list.extend(errors)
