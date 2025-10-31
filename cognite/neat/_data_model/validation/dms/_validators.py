from itertools import chain

from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import DirectNodeRelation
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    DataModelReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation


class ViewsWithoutProperties(DataModelValidator):
    """This validator checks for views without properties, i.e. views that do not have any
    property attached to them , either directly or through implements."""

    code = "NEAT-DMS-001"

    def __init__(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

    def run(self) -> list[ConsistencyError]:
        views_without_properties = []

        for ref, view in self.local_views_by_reference.items():
            if not view.properties:
                # Existing CDF view has properties
                if (
                    self.cdf_views_by_reference
                    and (remote := self.cdf_views_by_reference.get(ref))
                    and remote.properties
                ):
                    continue

                # Implemented views have properties
                if view.implements and any(
                    self.cdf_views_by_reference
                    and (remote_implement := self.cdf_views_by_reference.get(implement))
                    and remote_implement.properties
                    for implement in view.implements or []
                ):
                    continue

                views_without_properties.append(ref)

        return [
            ConsistencyError(
                message=(
                    f"View {ref!s} does "
                    "not have any properties defined, either directly or through implements."
                    " This will prohibit your from deploying the data model to CDF."
                ),
                fix="Define properties for the view",
                code=self.code,
            )
            for ref in views_without_properties
        ]


class UndefinedConnectionEndNodeTypes(DataModelValidator):
    """This validator checks for connections where the end node types are not defined"""

    code = "NEAT-DMS-002"

    def __init__(
        self,
        local_connection_end_node_types: dict[tuple[ViewReference, str], ViewReference],
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_connection_end_node_types = local_connection_end_node_types
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

    def run(self) -> list[ConsistencyError]:
        undefined_value_types = []

        for (view, property_), value_type in self.local_connection_end_node_types.items():
            if value_type not in self.local_views_by_reference and value_type not in self.cdf_views_by_reference:
                undefined_value_types.append((view, property_, value_type))

        return [
            ConsistencyError(
                message=(
                    f"View {view!s} property {property_!s} has value type {value_type!s} "
                    "which is not defined as a view in the data model neither exists in CDF."
                    " This will prohibit you from deploying the data model to CDF."
                ),
                fix="Define necessary view",
                code=self.code,
            )
            for (view, property_, value_type) in undefined_value_types
        ]


class VersionSpaceInconsistency(DataModelValidator):
    """This validator checks for inconsistencies in versioning and space among views and data model"""

    code = "NEAT-DMS-003"

    def __init__(
        self,
        data_model_reference: DataModelReference,
        view_references: list[ViewReference],
    ) -> None:
        self.data_model_reference = data_model_reference
        self.view_references = view_references

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.view_references:
            issue_description = ""

            if view_ref.space not in COGNITE_SPACES:
                # notify about inconsisten space
                if view_ref.space != self.data_model_reference.space:
                    issue_description = f"space (view: {view_ref.space}, data model: {self.data_model_reference.space})"

                # or version if spaces are same
                elif view_ref.version != self.data_model_reference.version:
                    issue_description = (
                        f"version (view: {view_ref.version}, data model: {self.data_model_reference.version})"
                    )

            if issue_description:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View {view_ref!s} has inconsistent {issue_description} "
                            "with the data model."
                            " This may lead to more demanding development and maintenance efforts."
                        ),
                        fix="Update view version and/or space to match data model",
                        code=self.code,
                    )
                )

        return recommendations


class BidirectionalConnectionMisconfigured(DataModelValidator):
    """This validator checks for bidirectional connections, reverse - direct pairs, where the direct part of the
    connection is not configured in a way that it points back to the reverse connection's view.

    Some examples of misconfigurations are:
    - A reverse connection points to a view through a property (direct connection) which in turn points to another
      view (results in Consistency Error)
    - A direct part of a bidirectional value type is not configured as a direct relation property (results in
      Consistency Error)
    - A direct part of a bidirectional value type is None (results in Recommendation)

    The latter misconfiguration is a hack used by users to create a multi value direct relations. This
    allows users to create multiple reverse direct relations through this property. In CDF Search this will give
    you a multi value direct relation.
    """

    code = "NEAT-DMS-004"

    def __init__(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
        reverse_to_direct_mapping: dict[
            tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
        ],
        local_containers_by_reference: dict[ContainerReference, ContainerRequest],
        cdf_containers_by_reference: dict[ContainerReference, ContainerRequest],
    ) -> None:
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference
        self.reverse_to_direct_mapping = reverse_to_direct_mapping
        self.local_containers_by_reference = local_containers_by_reference
        self.cdf_containers_by_reference = cdf_containers_by_reference

    def _select_source_view(self, view_ref: ViewReference, through: ViewDirectReference) -> ViewRequest | None:
        """Select the appropriate view (local or CDF) that contains the property."""
        local_view = self.local_views_by_reference.get(view_ref)
        cdf_view = self.cdf_views_by_reference.get(view_ref)

        # Try views with the property first, then any available view
        candidates = chain(
            (v for v in (local_view, cdf_view) if v and v.properties and through.identifier in v.properties),
            (v for v in (local_view, cdf_view) if v),
        )

        return next(candidates, None)

    def _select_source_container(
        self, container_ref: ContainerReference, container_property: str
    ) -> ContainerRequest | None:
        """Select the appropriate container (local or CDF) that contains the property."""
        local_container = self.local_containers_by_reference.get(container_ref)
        cdf_container = self.cdf_containers_by_reference.get(container_ref)

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (local_container, cdf_container) if c and c.properties and container_property in c.properties),
            (c for c in (local_container, cdf_container) if c),
        )

        return next(candidates, None)

    def _container_to_view_direct_reference(
        self, view_ref: ViewReference, container_direct_ref: ContainerDirectReference
    ) -> ViewDirectReference | None:
        properties = chain(
            (local_view.properties or {}).items()
            if (local_view := self.local_views_by_reference.get(view_ref))
            else {},
            (cdf_view.properties or {}).items() if (cdf_view := self.cdf_views_by_reference.get(view_ref)) else {},
        )
        for property_ref, property_ in properties:
            if (
                isinstance(property_, ViewCorePropertyRequest)
                and property_.container == container_direct_ref.source
                and property_.container_property_identifier == container_direct_ref.identifier
            ):
                return ViewDirectReference(source=view_ref, identifier=property_ref)

        return None

    def run(self) -> list[ConsistencyError | Recommendation]:
        issues: list[ConsistencyError | Recommendation] = []

        for (target_view_ref, reverse_prop_name), (source_view_ref, through) in self.reverse_to_direct_mapping.items():
            if isinstance(through, ContainerDirectReference):
                modifed_through = self._container_to_view_direct_reference(source_view_ref, through)
                if not modifed_through:
                    issues.append(
                        ConsistencyError(
                            message=(
                                f"Source view {source_view_ref!s} is missing a property that maps to "
                                f"container {through.source!s} property '{through.identifier}'. "
                                f"This mapping is required to configure the reverse connection "
                                f"'{reverse_prop_name}' in target view {target_view_ref!s}."
                            ),
                            fix="Add a view property that maps to the container property",
                            code=self.code,
                        )
                    )
                    continue
                through = modifed_through

            # attempt to select the source view that contains the property either locally or in CDF
            source_view = self._select_source_view(source_view_ref, through)

            # This should be caught by UndefinedConnectionEndNodeTypes as well
            if not source_view:
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} used to configure reverse connection "
                            f"'{reverse_prop_name}' in target view {target_view_ref!s} "
                            "does not exist in the data model or CDF."
                        ),
                        fix="Define the missing source view",
                        code=self.code,
                    )
                )
                continue

            # This should be caught by ViewsWithoutProperties as well
            if not source_view.properties or not (source_property := source_view.properties.get(through.identifier)):
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} is missing property '{through.identifier}' "
                            f"which is required to configure the reverse connection "
                            f"'{reverse_prop_name}' in target view {target_view_ref!s}."
                        ),
                        fix="Add the missing property to the source view",
                        code=self.code,
                    )
                )
                continue

            # source property exists, but it is not a direct relation property
            if not isinstance(source_property, ViewCorePropertyRequest):
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} property '{through.identifier}' "
                            f"used for configuring the reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s} is not a direct connection property."
                        ),
                        fix="Update view property to be a direct connection property",
                        code=self.code,
                    )
                )
                continue

            # Here we start checking if the direct connection property is mapped to the container property
            container_ref, container_property_identifier = (
                source_property.container,
                source_property.container_property_identifier,
            )

            source_container = self._select_source_container(container_ref, container_property_identifier)

            if not source_container:
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} is missing in both the data model and CDF. "
                            f"This container is required by view {source_view_ref!s}"
                            f" property '{through.identifier}', "
                            f"which configures the reverse connection '{reverse_prop_name}'"
                            f" in target view {target_view_ref!s}."
                        ),
                        fix="Define the missing container",
                        code=self.code,
                    )
                )
                continue

            container_property = source_container.properties.get(container_property_identifier)

            if not container_property:
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} is missing property '{container_property_identifier}'. "
                            f"This property is required by the source view {source_view_ref!s}"
                            f" property '{through.identifier}', "
                            f"which configures the reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s}."
                        ),
                        fix="Add the missing property to the container",
                        code=self.code,
                    )
                )
                continue

            container_property_type = container_property.type

            if not isinstance(container_property_type, DirectNodeRelation):
                issues.append(
                    ConsistencyError(
                        message=(
                            f"Container property '{container_property_identifier}' in container {container_ref!s} "
                            f"must be a direct connection, but found type '{container_property_type!s}'. "
                            f"This property is used by source view {source_view_ref!s} property '{through.identifier}' "
                            f"to configure reverse connection '{reverse_prop_name}' in target view {target_view_ref!s}."
                        ),
                        fix="Change container property type to be a direct connection",
                        code=self.code,
                    )
                )
                continue

            actual_target_view = source_property.source

            # Typical hack used to make SEARCH to work
            if not actual_target_view:
                issues.append(
                    Recommendation(
                        message=(
                            f"Source view {source_view_ref!s} property '{through.identifier}' "
                            f"has no target view specified (value type is None). "
                            f"This property is used for reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s}. "
                            f"While this works as a hack for multi-value relations in CDF Search, "
                            f"it's recommended to explicitly define the target view as {target_view_ref!s}."
                        ),
                        fix="Set the property's value type to the target view for better clarity",
                        code=self.code,
                    )
                )
                continue

            # Finnally check that the direct connection points to the correct target view
            if actual_target_view != target_view_ref:
                issues.append(
                    ConsistencyError(
                        message=(
                            f"The reverse connection '{reverse_prop_name}' in view {target_view_ref!s} "
                            f"expects its corresponding direct connection in view {source_view_ref!s} "
                            f"(property '{through.identifier}') to point back to {target_view_ref!s}, "
                            f"but it actually points to {actual_target_view!s}."
                        ),
                        fix="Update the direct connection property to point back to the correct target view",
                        code=self.code,
                    )
                )

        return issues
