"""Validators for checking performance-related aspects of the data model."""

from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-PERFORMANCE"


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
    Without a requires hierarchy, queries on views with multiple containers may perform
    expensive joins. With a proper requires hierarchy, the query optimizer can use more
    efficient execution plans.

    ## Example
    View `Pump` maps to containers `Pump` and `CogniteDescribable`.
    If neither container requires the other, queries may be slower.
    Adding `Pump requires CogniteDescribable` allows query optimization.
    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.local.views:
            containers_in_view = self.validation_resources.view_to_containers.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue  # Single container or no containers - no hierarchy needed

            # Check if there's a container that requires all others (directly or indirectly)
            if self.validation_resources.has_full_requires_hierarchy(containers_in_view):
                continue  # Hierarchy is complete, no recommendation needed

            # Try to find a clear "outermost" container for targeted recommendations
            outermost = self.validation_resources.find_outermost_container(containers_in_view)

            if outermost:
                # Generate targeted recommendations for this outermost container
                transitively_required = self.validation_resources.get_transitively_required_containers(outermost)
                missing = containers_in_view - transitively_required - {outermost}

                # Find minimal set of containers that need requires constraints
                minimal_missing = self.validation_resources.find_minimal_requires_container_set(missing)
                # Only include chain containers that are actually in this view
                chain_containers = (transitively_required | {outermost}) & containers_in_view

                for target in sorted(minimal_missing, key=str):
                    # Check if there's a bridge container that already requires target
                    bridge_result = self.validation_resources.find_bridge_and_requirer(
                        target,
                        chain_containers=chain_containers,
                        containers_in_scope=containers_in_view,
                    )

                    if bridge_result:
                        require_target, requirer = bridge_result
                    else:
                        requirer = outermost
                        require_target = target

                    recommendations.append(
                        Recommendation(
                            message=(
                                f"View '{view_ref!s}': Container '{requirer!s}' should require "
                                f"'{require_target!s}' to enable query optimization."
                            ),
                            fix="Add requires constraints between the containers",
                            code=self.code,
                        )
                    )
            else:
                # No clear outermost container - try to find the best candidate among unrequired containers
                uncovered = self.validation_resources.find_unrequired_containers(containers_in_view)

                if len(uncovered) > 1:
                    # Find which unrequired container already covers the most via existing requires
                    # This container is the best candidate for others to require
                    get_coverage = self.validation_resources.get_transitively_required_containers
                    best_candidate = max(uncovered, key=lambda c: len(get_coverage(c)))
                    best_coverage = len(get_coverage(best_candidate))

                    if best_coverage > 0:
                        # This container already has requires, recommend others require it
                        others = uncovered - {best_candidate}
                        for other in sorted(others, key=str):
                            recommendations.append(
                                Recommendation(
                                    message=(
                                        f"View '{view_ref!s}': Container '{other!s}' should require "
                                        f"'{best_candidate!s}' to enable query optimization."
                                    ),
                                    fix="Add requires constraints between the containers",
                                    code=self.code,
                                )
                            )
                    else:
                        # No container has existing requires, use generic message
                        uncovered_str = ", ".join(f"'{c!s}'" for c in sorted(uncovered, key=str))
                        recommendations.append(
                            Recommendation(
                                message=(
                                    f"View '{view_ref!s}' maps to {len(containers_in_view)} containers but no single "
                                    f"container requires all the others (directly or indirectly). "
                                    f"Containers without requires constraints between them: {uncovered_str}. "
                                    "This can cause suboptimal query performance."
                                ),
                                fix="Add requires constraints between the containers",
                                code=self.code,
                            )
                        )

        return recommendations
