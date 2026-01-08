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

        # Pre-compute conflicting containers to avoid contradictory recommendations
        conflicting_containers = self.validation_resources.conflicting_containers

        for view_ref in self.validation_resources.merged.views:
            containers_in_view = self.validation_resources.view_to_containers.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue  # Single container or no containers - no hierarchy needed

            # Skip if hierarchy is already complete
            if self.validation_resources.has_full_requires_hierarchy(containers_in_view):
                continue

            # Skip views handled by UnresolvableQueryPerformanceIssue
            user_containers = [c for c in containers_in_view if c.space not in CDF_BUILTIN_SPACES]
            if not user_containers:
                continue  # All CDF built-in containers - handled by other validator

            conflicting_in_view = containers_in_view & conflicting_containers
            if conflicting_in_view:
                continue  # Has conflicting containers - handled by other validator

            # Get missing requires from the globally optimal tree (computed once, cached)
            missing_requires = self.validation_resources.get_missing_requires_for_view(containers_in_view)

            # Generate targeted recommendations for each missing constraint
            for src, dst in sorted(missing_requires, key=lambda x: (str(x[0]), str(x[1]))):
                # Check if this recommendation might affect other views
                affected_views = self.validation_resources.find_views_affected_by_requires(
                    src, dst, exclude_view=view_ref
                )

                if affected_views:
                    # Find "superset" views that contain both src and dst
                    # These can serve as ingestion points for the affected views
                    # Note: At least one superset view always exists because recommendations
                    # only come from container pairs that appear together in some view
                    superset_views = self.validation_resources.find_views_with_both_containers(src, dst)
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

        return recommendations


class UnresolvableQueryPerformanceIssue(DataModelValidator):
    """
    Identifies views with query performance issues that cannot be resolved with requires constraints.

    ## What it does
    Detects two types of unsolvable query performance issues:

    1. **CDF-only containers**: Views that map only to CDF built-in containers without a complete
       requires hierarchy. Since users cannot modify CDF containers, no requires can be added.

    2. **Conflicting containers**: Views containing a container that appears in multiple views
       with different sibling containers. Adding a requires to any sibling would break ingestion
       for other views using the same container.

    ## Why is this bad?
    These views will have suboptimal query performance that cannot be fixed by adding requires
    constraints. The only solutions are to restructure the views or add a new container specific
    to the view that requires the others.

    ## Example
    - CogniteExtractorData appears in CogniteExtractorFile (with CogniteFile) and
      CogniteExtractorTimeSeries (with CogniteTimeSeries).
    - If CogniteExtractorData requires CogniteFile, CogniteExtractorTimeSeries breaks.
    - If CogniteExtractorData requires CogniteTimeSeries, CogniteExtractorFile breaks.
    """

    code = f"{BASE_CODE}-002"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        conflicting_containers = self.validation_resources.conflicting_containers

        for view_ref in self.validation_resources.merged.views:
            # Skip CDF built-in views
            if view_ref.space in CDF_BUILTIN_SPACES:
                continue

            containers_in_view = self.validation_resources.view_to_containers.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue

            # Skip if hierarchy is already complete
            if self.validation_resources.has_full_requires_hierarchy(containers_in_view):
                continue

            user_containers = [c for c in containers_in_view if c.space not in CDF_BUILTIN_SPACES]
            conflicting_in_view = containers_in_view & conflicting_containers

            # Case 1: All containers are CDF built-in (not modifiable)
            if not user_containers:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                            f"The view maps only to CDF built-in containers which cannot be modified to add requires constraints. "
                            f"Consider restructuring the view or adding another container with at least one property to this view that requires the others."
                        ),
                        fix="Add a container with at least one property that requires the others, or restructure the view",
                        code=self.code,
                    )
                )

            # Case 2: Has conflicting containers
            elif conflicting_in_view:
                conflicting_names = ", ".join(f"'{c!s}'" for c in sorted(conflicting_in_view, key=str))
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                            f"Container {conflicting_names} appears in multiple views with different sibling containers, "
                            f"making it impossible to optimize performance without breaking ingestion for other views. "
                            f"Consider adding a view-specific container with at least one property that requires the others."
                        ),
                        fix="Add a container with at least one property that requires the others, or restructure the view",
                        code=self.code,
                    )
                )

        return recommendations
