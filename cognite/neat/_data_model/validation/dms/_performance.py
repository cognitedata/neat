"""Validators for checking performance-related aspects of the data model."""

from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES
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

    Uses Minimum Spanning Arborescence (Edmonds' algorithm) to find the optimal set of requires
    constraints that completes the hierarchy with minimal "cost", where cost is based on:
    - How often containers appear together in views (prefer common pairs)
    - Whether containers are user vs CDF built-in (prefer user containers)
    - Existing transitivity (leverage existing requires chains)

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

        for view_ref in self.validation_resources.merged.views:
            containers_in_view = self.validation_resources.view_to_containers.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue  # Single container or no containers - no hierarchy needed

            # Skip if hierarchy is already complete
            if self.validation_resources.has_full_requires_hierarchy(containers_in_view):
                continue

            # Get missing requires from the globally optimal tree (computed once, cached)
            missing_requires = self.validation_resources.get_missing_requires_for_view(containers_in_view)

            if missing_requires:
                # Generate targeted recommendations for each missing constraint
                for src, dst in sorted(missing_requires, key=lambda x: (str(x[0]), str(x[1]))):
                    # Check if this recommendation might affect other views
                    affected_views = self.validation_resources.find_views_affected_by_requires(
                        src, dst, exclude_view=view_ref
                    )

                    if affected_views:
                        # Check if there are "superset" views that contain both src and dst
                        # These can serve as ingestion points for the affected views
                        superset_views = self.validation_resources.find_views_with_both_containers(src, dst)
                        # Exclude the current view from superset consideration
                        superset_views = superset_views - {view_ref}

                        if superset_views:
                            # Dependency case: affected views will depend on superset views
                            superset_example = min(superset_views, key=str)
                            recommendations.append(
                                Recommendation(
                                    message=(
                                        f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}' to mitigate this. "
                                        f"Note that this will make populating instances through this view dependent on '{src!s}' being populated "
                                        f"separately first, or through a view that maps to both (e.g., '{superset_example!s}')."
                                    ),
                                    fix="Add requires constraints between the containers",
                                    code=self.code,
                                )
                            )
                        else:
                            # No superset view exists - truly problematic case
                            affected_names = ", ".join(str(v) for v in sorted(affected_views, key=str)[:3])
                            if len(affected_views) > 3:
                                affected_names += f" and {len(affected_views) - 3} more"
                            recommendations.append(
                                Recommendation(
                                    message=(
                                        f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}' to mitigate this. "
                                        f"Note that this will make populating instances through {affected_names} "
                                        f"dependent on '{dst!s}' being populated first."
                                    ),
                                    fix="Add requires constraints between the containers",
                                    code=self.code,
                                )
                            )
                    else:
                        recommendations.append(
                            Recommendation(
                                message=(
                                    f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                                    f"Add a 'requires' constraint from '{src!s}' to '{dst!s}' to mitigate this."
                                ),
                                fix="Add requires constraints between the containers",
                                code=self.code,
                            )
                        )
            elif view_ref.space not in CDF_BUILTIN_SPACES:
                # No recommendations but hierarchy is incomplete - unsolvable case
                # This happens when all mapped containers are CDF built-in (not modifiable)
                user_containers = [c for c in containers_in_view if c.space not in CDF_BUILTIN_SPACES]
                if not user_containers:
                    recommendations.append(
                        Recommendation(
                            message=(
                                f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                                f"The view maps to multiple CDF built-in containers {', '.join(str(c) for c in containers_in_view)} "
                                " without a complete requires hierarchy between them, but because these containers are not modifiable, "
                                " this cannot be fixed by adding requires constraints."
                            ),
                            fix="Consider restructuring the view",
                            code=self.code,
                        )
                    )

        return recommendations
