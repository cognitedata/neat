from dataclasses import dataclass
from itertools import chain

from pyparsing import cast

from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import DataType, DirectNodeRelation
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation


@dataclass
class ReverseConnectionContext:
    """Context for validating a bidirectional connection."""

    target_view_ref: ViewReference
    reverse_prop_name: str
    source_view_ref: ViewReference
    through: ViewDirectReference


class BidirectionalConnectionMisconfigured(DataModelValidator):
    """This validator checks bidirectional connections to ensure reverse and direct connection pairs
    are properly configured.

    A bidirectional connection consists of:
    - A reverse connection property in a target view, pointing to a source view through a direct connection property
    - A corresponding direct connection property in a source view that points back to the target view

    Example:
        View A has property "relatedB" (reverse) → through View B property "relatedA" (direct)
        View B has property "relatedA" (direct) → points back to View A

    Validation checks:
        1. Source view and property exist
        2. Property is a direct connection type
        3. Container mapping is correct
        4. Direct connection points back to correct target
    """

    code = "NEAT-DMS-004"

    def run(self) -> list[ConsistencyError | Recommendation]:
        """Run validation and return list of issues found."""
        issues: list[ConsistencyError | Recommendation] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = self._normalize_through_reference(source_view_ref, through)
            context = ReverseConnectionContext(target_view_ref, reverse_prop_name, source_view_ref, through)
            issues.extend(self._validate_bidirectional_connection(context))

        return issues

    def _validate_bidirectional_connection(
        self, ctx: ReverseConnectionContext
    ) -> list[ConsistencyError] | list[Recommendation]:
        """Validate a single bidirectional connection pair.

        Args:
            ctx: Connection context containing all necessary references

        Returns:
            List of validation issues found
        """

        # Validate source view exists
        source_view = self._select_source_view(ctx.source_view_ref, ctx.through)
        if error := self._check_source_view_exists(source_view, ctx):
            return [error]

        source_view: ViewRequest  # for type checker, since we checked for None above
        # Validate source property exists and is correct type
        if error := self._check_source_property(source_view, ctx):
            return [error]

        source_property = cast(ViewCorePropertyRequest, source_view.properties[ctx.through.identifier])

        # Validate container mapping
        if container_errors := self._validate_container_mapping(source_property, ctx):
            return container_errors

        # Validate target view reference
        return self._validate_target_reference(source_property, ctx)

    def _normalize_through_reference(
        self, source_view_ref: ViewReference, through: ContainerDirectReference | ViewDirectReference
    ) -> ViewDirectReference:
        """Normalize through reference to ViewDirectReference for consistent processing."""

        if isinstance(through, ContainerDirectReference):
            return ViewDirectReference(source=source_view_ref, identifier=through.identifier)
        return through

    def _select_source_view(self, view_ref: ViewReference, through: ViewDirectReference) -> ViewRequest | None:
        """Select the appropriate view (local or CDF) that contains the property used in the reverse connection.

        Prioritizes views that contain the property, then falls back to any available view.
        """
        local_view = self.local_resources.views_by_reference.get(view_ref)
        cdf_view = self.cdf_resources.views_by_reference.get(view_ref)

        # Try views with the property first, then any available view
        candidates = chain(
            (v for v in (local_view, cdf_view) if v and v.properties and through.identifier in v.properties),
            (v for v in (local_view, cdf_view) if v),
        )

        return next(candidates, None)

    def _select_source_container(
        self, container_ref: ContainerReference, container_property: str
    ) -> ContainerRequest | None:
        """Select the appropriate container (local or CDF) that contains the property.

        Prioritizes containers that contain the property, then falls back to any available container.
        """
        local_container = self.local_resources.containers_by_reference.get(container_ref)
        cdf_container = self.cdf_resources.containers_by_reference.get(container_ref)

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (local_container, cdf_container) if c and c.properties and container_property in c.properties),
            (c for c in (local_container, cdf_container) if c),
        )

        return next(candidates, None)

    def _check_source_view_exists(
        self, source_view: ViewRequest | None, ctx: ReverseConnectionContext
    ) -> "ConsistencyError | None":
        """Check if source view exists."""
        if not source_view:
            return self._create_missing_view_error(ctx)
        return None

    def _check_source_property(
        self, source_view: ViewRequest, ctx: ReverseConnectionContext
    ) -> "ConsistencyError | None":
        """Check if source property exists and is of correct type."""
        if not source_view.properties:
            return self._create_missing_property_error(ctx)

        source_property = source_view.properties.get(ctx.through.identifier)
        if not source_property:
            return self._create_missing_property_error(ctx)

        if not isinstance(source_property, ViewCorePropertyRequest):
            return self._create_wrong_property_type_error(ctx)

        return None

    def _validate_container_mapping(
        self, source_property: ViewCorePropertyRequest, ctx: ReverseConnectionContext
    ) -> list[ConsistencyError]:
        """Validate that the container and container property are correctly configured."""
        container_ref = source_property.container
        container_property_id = source_property.container_property_identifier

        source_container = self._select_source_container(container_ref, container_property_id)
        if not source_container:
            return [self._create_missing_container_error(container_ref, ctx)]

        container_property = source_container.properties.get(container_property_id)
        if not container_property:
            return [self._create_missing_container_property_error(container_ref, container_property_id, ctx)]

        if not isinstance(container_property.type, DirectNodeRelation):
            return [
                self._create_wrong_container_type_error(
                    container_ref, container_property_id, container_property.type, ctx
                )
            ]

        return []

    def _validate_target_reference(
        self, source_property: ViewCorePropertyRequest, ctx: ReverseConnectionContext
    ) -> list[ConsistencyError] | list[Recommendation]:
        """Validate that the direct connection points back to the correct target view."""
        actual_target_view = source_property.source

        # Check for missing target view (SEARCH hack)
        if not actual_target_view:
            return [self._create_missing_target_recommendation(ctx)]

        # Check if pointing to ancestor
        if self._is_ancestor_of_target(actual_target_view, ctx.target_view_ref):
            return [self._create_ancestor_recommendation(actual_target_view, ctx)]

        # Check if pointing to wrong view
        if actual_target_view != ctx.target_view_ref:
            return [self._create_wrong_target_error(actual_target_view, ctx)]

        return []

    def _is_ancestor_of_target(self, potential_ancestor: ViewReference, target_view_ref: ViewReference) -> bool:
        """Check if a view is an ancestor of the target view."""
        return potential_ancestor in self.local_resources.ancestors_by_view_reference.get(
            target_view_ref, set()
        ) or potential_ancestor in self.cdf_resources.ancestors_by_view_reference.get(target_view_ref, set())

    # Error and Recommendation creation methods
    def _create_missing_view_error(self, ctx: ReverseConnectionContext) -> ConsistencyError:
        """Create error for missing source view."""
        return ConsistencyError(
            message=(
                f"Source view {ctx.source_view_ref!s} used to configure reverse connection "
                f"'{ctx.reverse_prop_name}' in target view {ctx.target_view_ref!s} "
                "does not exist in the data model or CDF."
            ),
            fix="Define the missing source view",
            code=self.code,
        )

    def _create_missing_property_error(self, ctx: ReverseConnectionContext) -> ConsistencyError:
        """Create error for missing source property."""
        return ConsistencyError(
            message=(
                f"Source view {ctx.source_view_ref!s} is missing property '{ctx.through.identifier}' "
                f"which is required to configure the reverse connection "
                f"'{ctx.reverse_prop_name}' in target view {ctx.target_view_ref!s}."
            ),
            fix="Add the missing property to the source view",
            code=self.code,
        )

    def _create_wrong_property_type_error(self, ctx: ReverseConnectionContext) -> ConsistencyError:
        """Create error for incorrect property type."""
        return ConsistencyError(
            message=(
                f"Source view {ctx.source_view_ref!s} property '{ctx.through.identifier}' "
                f"used for configuring the reverse connection '{ctx.reverse_prop_name}' "
                f"in target view {ctx.target_view_ref!s} is not a direct connection property."
            ),
            fix="Update view property to be a direct connection property",
            code=self.code,
        )

    def _create_missing_container_error(
        self, container_ref: ContainerReference, ctx: ReverseConnectionContext
    ) -> ConsistencyError:
        """Create error for missing container."""
        return ConsistencyError(
            message=(
                f"Container {container_ref!s} is missing in both the data model and CDF. "
                f"This container is required by view {ctx.source_view_ref!s}"
                f" property '{ctx.through.identifier}', "
                f"which configures the reverse connection '{ctx.reverse_prop_name}'"
                f" in target view {ctx.target_view_ref!s}."
            ),
            fix="Define the missing container",
            code=self.code,
        )

    def _create_missing_container_property_error(
        self, container_ref: ContainerReference, container_property_id: str, ctx: ReverseConnectionContext
    ) -> ConsistencyError:
        """Create error for missing container property."""
        return ConsistencyError(
            message=(
                f"Container {container_ref!s} is missing property '{container_property_id}'. "
                f"This property is required by the source view {ctx.source_view_ref!s}"
                f" property '{ctx.through.identifier}', "
                f"which configures the reverse connection '{ctx.reverse_prop_name}' "
                f"in target view {ctx.target_view_ref!s}."
            ),
            fix="Add the missing property to the container",
            code=self.code,
        )

    def _create_wrong_container_type_error(
        self,
        container_ref: ContainerReference,
        container_property_id: str,
        actual_type: DataType,
        ctx: ReverseConnectionContext,
    ) -> ConsistencyError:
        """Create error for incorrect container property type."""
        return ConsistencyError(
            message=(
                f"Container property '{container_property_id}' in container {container_ref!s} "
                f"must be a direct connection, but found type '{actual_type!s}'. "
                f"This property is used by source view {ctx.source_view_ref!s} property '{ctx.through.identifier}' "
                f"to configure reverse connection '{ctx.reverse_prop_name}' in target view {ctx.target_view_ref!s}."
            ),
            fix="Change container property type to be a direct connection",
            code=self.code,
        )

    def _create_missing_target_recommendation(self, ctx: ReverseConnectionContext) -> Recommendation:
        """Create recommendation for missing target view (SEARCH hack)."""
        return Recommendation(
            message=(
                f"Source view {ctx.source_view_ref!s} property '{ctx.through.identifier}' "
                f"has no target view specified (value type is None). "
                f"This property is used for reverse connection '{ctx.reverse_prop_name}' "
                f"in target view {ctx.target_view_ref!s}. "
                f"While this works as a hack for multi-value relations in CDF Search, "
                f"it's recommended to explicitly define the target view as {ctx.target_view_ref!s}."
            ),
            fix="Set the property's value type to the target view for better clarity",
            code=self.code,
        )

    def _create_ancestor_recommendation(
        self, actual_target_view: ViewReference, ctx: ReverseConnectionContext
    ) -> Recommendation:
        """Create recommendation when direct connection points to ancestor."""
        return Recommendation(
            message=(
                f"The direct connection property '{ctx.through.identifier}' in view {ctx.source_view_ref!s} "
                f"configures the reverse connection '{ctx.reverse_prop_name}' in {ctx.target_view_ref!s}. "
                f"Therefore, it is expected that '{ctx.through.identifier}' points to {ctx.target_view_ref!s}. "
                f"However, it currently points to {actual_target_view!s}, which is an ancestor of "
                f"{ctx.target_view_ref!s}. "
                "While this will allow for model to be valid, it can be a source of confusion and mistakes."
            ),
            fix="Update the direct connection property to point to the target view instead of its ancestor",
            code=self.code,
        )

    def _create_wrong_target_error(
        self, actual_target_view: ViewReference, ctx: ReverseConnectionContext
    ) -> ConsistencyError:
        """Create error when direct connection points to wrong view."""
        return ConsistencyError(
            message=(
                f"The reverse connection '{ctx.reverse_prop_name}' in view {ctx.target_view_ref!s} "
                f"expects its corresponding direct connection in view {ctx.source_view_ref!s} "
                f"(property '{ctx.through.identifier}') to point back to {ctx.target_view_ref!s}, "
                f"but it actually points to {actual_target_view!s}."
            ),
            fix="Update the direct connection property to point back to the correct target view",
            code=self.code,
        )
