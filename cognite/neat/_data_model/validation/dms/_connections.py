from dataclasses import dataclass

from pyparsing import cast

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

_BASE_CODE = "NEAT-DMS-CONNECTIONS"


class ConnectionValueTypeExist(DataModelValidator):
    """This validator checks whether connections value types (end node types) exist in the data model or in CDF."""

    code = f"{_BASE_CODE}-001"

    def run(self) -> list[ConsistencyError]:
        undefined_value_types = []

        for (view, property_), value_type in self.local_resources.connection_end_node_types.items():
            if value_type is None:
                continue

            if value_type in self.local_resources.views_by_reference:
                continue

            if (
                self.modus_operandi == "additive" or value_type.space != self.local_resources.data_model_reference.space
            ) and value_type in self.cdf_resources.views_by_reference:
                continue

            undefined_value_types.append((view, property_, value_type))

        return [
            ConsistencyError(
                message=(
                    f"View {view!s} connection {property_!s} has value type {value_type!s} "
                    "which is not defined as a view in the data model neither exists in CDF."
                    " This will prohibit you from deploying the data model to CDF."
                ),
                fix="Define necessary view",
                code=self.code,
            )
            for (view, property_, value_type) in undefined_value_types
        ]


class ConnectionValueTypeNotNone(DataModelValidator):
    """This validator checks whether connection value types are not None."""

    code = f"{_BASE_CODE}-002"

    def run(self) -> list[Recommendation]:
        missing_value_types = []

        for (view, property_), value_type in self.local_resources.connection_end_node_types.items():
            if not value_type:
                missing_value_types.append((view, property_))

        return [
            Recommendation(
                message=(
                    f"View {view!s} connection {property_!s} is missing value type (end node type)."
                    " This yields ambiguous data model definition."
                ),
                fix="Define necessary value type",
                code=self.code,
            )
            for (view, property_) in missing_value_types
        ]


@dataclass
class ReverseConnectionContext:
    """Context for validating a bidirectional connection.
    This context holds all necessary references to validate the connection.

    Attributes:
        target_view_ref: Reference to the target view containing the reverse property.
        reverse_property: Identifier of the reverse property in the target view.
        through: Direct reference defining the direct property used in the reverse connection.
        source_view_ref: Reference to the source view containing the direct property, to which the reverse points.


    Example:
        View `WindTurbine` has property `windFarm` (direct) → points to View `WindFarm`
        View `WindFarm` has property `turbines` (reverse) → points to View `WindTurbine` through `WindTurbine.windFarm`
    """

    target_view_ref: ViewReference
    reverse_property: str
    through: ViewDirectReference
    source_view_ref: ViewReference


class BidirectionalConnectionMisconfigured(DataModelValidator):
    """This validator checks bidirectional connections to ensure reverse and direct connection pairs
    are properly configured.

    A bidirectional connection consists of:
    - A direct connection property in a source view that points to the target view
      SourceView -- [directConnection] --> TargetView
    - A reverse connection property in a target view, pointing to a source view through a direct connection property
      TargetView -- [reverseConnection, through(SourceView, SourceView.directConnection)] --> SourceView

    Validation checks:
        1. Source view and property exist
        2. Property is a direct connection type
        3. Container mapping is correct
        4. Direct connection points back to correct target
    """

    code = f"{_BASE_CODE}-003"

    def run(self) -> list[ConsistencyError | Recommendation]:
        """Run validation and return list of issues found."""
        issues: list[ConsistencyError | Recommendation] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = self._normalize_through_reference(source_view_ref, through)
            context = ReverseConnectionContext(target_view_ref, reverse_prop_name, through, source_view_ref)
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
        source_view = self._select_view_with_property(ctx.source_view_ref, ctx.through.identifier)

        if not source_view:
            return [self._create_missing_view_error(ctx)]

        if error := self._check_source_property(source_view, ctx):
            return [error]

        source_property = cast(ViewCorePropertyRequest, source_view.properties[ctx.through.identifier])

        # Validate container mapping
        if container_errors := self._check_container_property_type(source_property, ctx):
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

    def _check_container_property_type(
        self, source_property: ViewCorePropertyRequest, ctx: ReverseConnectionContext
    ) -> list[ConsistencyError]:
        """Validate that the container and container property are correctly configured."""
        container_ref = source_property.container
        container_property_id = source_property.container_property_identifier

        source_container = self._select_container_with_property(container_ref, container_property_id)
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
                f"'{ctx.reverse_property}' in target view {ctx.target_view_ref!s} "
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
                f"'{ctx.reverse_property}' in target view {ctx.target_view_ref!s}."
            ),
            fix="Add the missing property to the source view",
            code=self.code,
        )

    def _create_wrong_property_type_error(self, ctx: ReverseConnectionContext) -> ConsistencyError:
        """Create error for incorrect property type."""
        return ConsistencyError(
            message=(
                f"Source view {ctx.source_view_ref!s} property '{ctx.through.identifier}' "
                f"used for configuring the reverse connection '{ctx.reverse_property}' "
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
                f"which configures the reverse connection '{ctx.reverse_property}'"
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
                f"which configures the reverse connection '{ctx.reverse_property}' "
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
                f"to configure reverse connection '{ctx.reverse_property}' in target view {ctx.target_view_ref!s}."
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
                f"This property is used for reverse connection '{ctx.reverse_property}' "
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
                f"configures the reverse connection '{ctx.reverse_property}' in {ctx.target_view_ref!s}. "
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
                f"The reverse connection '{ctx.reverse_property}' in view {ctx.target_view_ref!s} "
                f"expects its corresponding direct connection in view {ctx.source_view_ref!s} "
                f"(property '{ctx.through.identifier}') to point back to {ctx.target_view_ref!s}, "
                f"but it actually points to {actual_target_view!s}."
            ),
            fix="Update the direct connection property to point back to the correct target view",
            code=self.code,
        )
