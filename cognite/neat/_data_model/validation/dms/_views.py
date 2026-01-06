"""Validators for checking views in the data model."""

from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

BASE_CODE = "NEAT-DMS-VIEW"


class ViewToContainerMappingNotPossible(DataModelValidator):
    """Validates that container and container property referenced by view property exist.

    ## What it does
    Validates that for each view property that maps to a container and container property,
    the referenced container and container property exist.

    ## Why is this bad?
    If a view property references a container or container property that does not exist,
    the data model cannot be deployed to CDF. This means that view property will not be able to function.

    ## Example
    View WindTurbine has property location that maps to container WindTurbineContainer and property gpsCoordinates.
    If WindTurbineContainer and/or property gpsCoordinates does not exist, the data model cannot be deployed to CDF.
    """

    code = f"{BASE_CODE}-001"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if not self.validation_resources.merged_data_model.views:
            return errors

        for view_ref in self.validation_resources.merged_data_model.views:
            view = self.validation_resources.select_view(view_ref)

            if not view:
                raise RuntimeError(
                    f"{type(self).__name__}: View {view_ref!s} not found in local resources. This is a bug in NEAT."
                )

            if view.properties is None:
                continue

            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                container_ref = property_.container
                container_property = property_.container_property_identifier

                container = self.validation_resources.select_container(container_ref, container_property)

                if not container:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} maps to "
                                f"container {container_ref!s} which does not exist."
                            ),
                            fix="Define necessary container",
                            code=self.code,
                        )
                    )
                elif container_property not in container.properties:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} maps to "
                                f"container {container_ref!s} which does not have "
                                f"property '{container_property}'."
                            ),
                            fix="Define necessary container property",
                            code=self.code,
                        )
                    )

        return errors


class ImplementedViewNotExisting(DataModelValidator):
    """Validates that implemented (inherited) view exists.

    ## What it does
    Validates that all views which are implemented (inherited) in the data model actually exist either locally
    or in CDF.

    ## Why is this bad?
    If a view being implemented (inherited) does not exist, the data model cannot be deployed to CDF.

    ## Example
    If view WindTurbine implements (inherits) view Asset, but Asset view does not exist in the data model
    or in CDF, the data model cannot be deployed to CDF.
    """

    code = f"{BASE_CODE}-002"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if not self.validation_resources.merged_data_model.views:
            return errors

        for view_ref in self.validation_resources.merged_data_model.views:
            view = self.validation_resources.select_view(view_ref)

            if not view:
                raise RuntimeError(
                    f"{type(self).__name__}: View {view_ref!s} not found in local resources. This is a bug in NEAT."
                )

            if view.implements is None:
                continue
            for implement in view.implements:
                if self.validation_resources.select_view(implement) is None:
                    errors.append(
                        ConsistencyError(
                            message=f"View {view_ref!s} implements {implement!s} which is not defined.",
                            fix="Define the missing view or remove it from the implemented views list",
                            code=self.code,
                        )
                    )

        return errors


class MappedContainersMissingRequiresConstraint(DataModelValidator):
    """
    Validates that views mapping to multiple containers have a requires hierarchy between them.

    ## What it does
    For each view that maps to two or more containers, this validator checks whether there is
    a complete hierarchy of requires constraints between all mapped containers. Specifically,
    there should be one "outermost" container that requires all others (directly or transitively).

    When possible, the validator identifies the appropriate "outermost" container and provides
    targeted recommendations for which specific requires constraints to add.

    ## Why is this bad?
    When querying a view without filters, the API uses `hasData` filters on all mapped containers.
    If there's no requires hierarchy, each container needs a separate `hasData` check, which
    triggers expensive joins. With a proper requires hierarchy, the `hasData` check can be
    optimized to only check the "outermost" container.

    ## Example
    View `Pump` maps to containers `Pump` and `CogniteDescribable`.
    If neither container requires the other, queries will perform two separate `hasData` checks
    with a join. Adding `Pump requires CogniteDescribable` allows the query
    optimizer to reduce this to a single `hasData` check.
    """

    code = f"{BASE_CODE}-003"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.local.views:
            containers_in_view = self.validation_resources.view_to_containers.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue  # Single container or no containers - no hierarchy needed

            # Check if there's a container that requires all others (directly or indirectly)
            if self.validation_resources.has_full_requires_hierarchy(containers_in_view):
                continue  # Performance optimization is possible

            # Try to find a clear "outermost" container for targeted recommendations
            outermost = self.validation_resources.find_outermost_container(containers_in_view)

            if outermost:
                # Generate targeted recommendations for this outermost container
                transitively_required = self.validation_resources.get_transitively_required_containers(outermost)
                missing = containers_in_view - transitively_required - {outermost}

                # Find minimal set of containers that need requires constraints
                minimal_missing = self.validation_resources.find_minimal_requires_set(missing)

                for target in sorted(minimal_missing, key=str):
                    recommendations.append(
                        Recommendation(
                            message=(
                                f"View '{view_ref!s}': Container '{outermost!s}' should require "
                                f"'{target!s}' to enable query optimization. "
                                f"Without this constraint, queries through this view use multiple hasData filters."
                            ),
                            fix=f"Add requires constraints between the containers",
                            code=self.code,
                        )
                    )
            else:
                # No clear outermost container - provide generic recommendation
                uncovered = self.validation_resources.find_unrequired_containers(containers_in_view)
                if len(uncovered) > 1:
                    uncovered_str = ", ".join(f"'{c!s}'" for c in sorted(uncovered, key=str))
                    recommendations.append(
                        Recommendation(
                            message=(
                                f"View '{view_ref!s}' maps to {len(containers_in_view)} containers but no single "
                                f"container requires all the others. The following containers are missing a requires "
                                f"constraint with another container: {uncovered_str}. "
                                f"This can cause suboptimal performance when querying instances through this view."
                            ),
                            fix=(
                                "Add requires constraints between the containers, such that one container "
                                "requires all the others, either directly or indirectly"
                            ),
                            code=self.code,
                        )
                    )

        return recommendations
