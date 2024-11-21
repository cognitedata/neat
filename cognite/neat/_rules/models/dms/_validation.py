from collections import defaultdict
from typing import Any, ClassVar, cast

from cognite.client import data_modeling as dm

from cognite.neat._constants import COGNITE_MODELS, DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat._issues import IssueList, NeatError, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import (
    PropertyDefinitionDuplicatedError,
    ResourceNotDefinedError,
)
from cognite.neat._issues.errors._properties import ReversedConnectionNotFeasibleError
from cognite.neat._issues.warnings import (
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
    UndefinedViewWarning,
)
from cognite.neat._issues.warnings.user_modeling import (
    NotNeatSupportedFilterWarning,
    ViewPropertyLimitWarning,
)
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ContainerEntity, RawFilter
from cognite.neat._rules.models.entities._single_value import (
    ReverseConnectionEntity,
    ViewEntity,
)

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
        self._validate_value_type_existence()
        self._validate_reverse_connections()

        self._referenced_views_and_containers_are_existing_and_proper_size()
        dms_schema = self.rules.as_schema()
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

        self.issue_list.extend(errors)

    def _referenced_views_and_containers_are_existing_and_proper_size(self) -> None:
        # TODO: Split this method and keep only validation that should be independent of
        # whether view and/or container exist in the pydantic model instance
        # other validation should be done through NeatSession.verify()
        defined_views = {view.view.as_id() for view in self.views}

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

        self.issue_list.extend(errors)

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

    def _validate_value_type_existence(self) -> None:
        views = {prop_.view for prop_ in self.properties}.union({view_.view for view_ in self.views})

        for prop_ in self.properties:
            if isinstance(prop_.value_type, ViewEntity) and prop_.value_type not in views:
                self.issue_list.append(
                    UndefinedViewWarning(
                        str(prop_.view),
                        str(prop_.value_type),
                        prop_.view_property,
                    )
                )

    def _validate_reverse_connections(self) -> None:
        # do not check for reverse connections in Cognite models
        if self.metadata.as_data_model_id() in COGNITE_MODELS:
            return None

        properties_by_ids = {f"{prop_.view!s}.{prop_.view_property}": prop_ for prop_ in self.properties}
        reversed_by_ids = {
            id_: prop_
            for id_, prop_ in properties_by_ids.items()
            if prop_.connection and isinstance(prop_.connection, ReverseConnectionEntity)
        }

        for id_, prop_ in reversed_by_ids.items():
            source_id = f"{prop_.value_type!s}." f"{cast(ReverseConnectionEntity, prop_.connection).property_}"
            if source_id not in properties_by_ids:
                print(f"source_id: {source_id}, first issue")
                self.issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        id_,
                        "reversed connection",
                        prop_.view_property,
                        str(prop_.view),
                        str(prop_.value_type),
                        cast(ReverseConnectionEntity, prop_.connection).property_,
                    )
                )

            elif source_id in properties_by_ids and properties_by_ids[source_id].value_type != prop_.view:
                print(f"source_id: {source_id}, second issue")
                self.issue_list.append(
                    ReversedConnectionNotFeasibleError(
                        id_,
                        "view property",
                        prop_.view_property,
                        str(prop_.view),
                        str(prop_.value_type),
                        cast(ReverseConnectionEntity, prop_.connection).property_,
                    )
                )

            else:
                continue

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
