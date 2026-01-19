"""Validators for checking performance-related aspects of the data model.

This module contains validators that check for query performance issues related to
container requires constraints:

- MissingRequiresConstraint: Add constraints to optimize query performance
- SuboptimalRequiresConstraint: Remove constraints not in the optimal structure
- UnresolvableQueryPerformance: Structural issues that can't be solved with requires
"""

from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-PERFORMANCE"


class MissingRequiresConstraint(DataModelValidator):
    """
    Recommends adding requires constraints to optimize query performance.

    ## What it does
    Identifies views where adding a requires constraint would improve query performance.
    The recommendation message indicates whether the change is "safe" (no cross-view
    dependencies) or requires attention to ingestion order.

    ## Why is this important?
    Views without proper requires constraints may have poor query performance.
    Adding requires constraints creates a connected hierarchy that enables efficient queries.

    ## Example
    View `Valve` needs `Tag → CogniteAsset` for optimization. The message will indicate
    if other views using `Tag` will also be affected by this change.
    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            containers_in_view = self.validation_resources.containers_by_view.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue

            user_containers = [c for c in containers_in_view if c.space not in COGNITE_SPACES]
            if not user_containers:
                continue

            to_add, _ = self.validation_resources.get_requires_changes_for_view(view_ref)

            if not to_add:
                continue

            for src, dst in to_add:
                src_views = self.validation_resources.views_by_container.get(src, set())
                other_views_with_src = src_views - {view_ref}
                superset_views = self.validation_resources.find_views_mapping_to_containers([src, dst])

                # Check if this is a "safe" recommendation (no cross-view dependencies)
                is_safe = not other_views_with_src or view_ref in superset_views

                if is_safe:
                    message = (
                        f"View '{view_ref!s}' is not optimized for querying. "
                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}'."
                    )
                else:
                    # Find a superset view to suggest for ingestion
                    # Prefer views matching the source container name (e.g., Tag view for Tag container)
                    superset_views = {v for v in superset_views if v in self.validation_resources.merged.views}
                    matching_view = next((v for v in superset_views if v.external_id == src.external_id), None)
                    superset_example = matching_view or (min(superset_views, key=str) if superset_views else view_ref)

                    message = (
                        f"View '{view_ref!s}' is not optimized for querying. "
                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}'. "
                        f"Note: this will require '{dst!s}' to be populated before '{src!s}', "
                        f"or ingest through a view that maps to both (e.g., '{superset_example!s}')."
                    )

                recommendations.append(
                    Recommendation(
                        message=message,
                        fix="Add requires constraint between the containers",
                        code=self.code,
                    )
                )

        return recommendations


class SuboptimalRequiresConstraint(DataModelValidator):
    """
    Recommends removing requires constraints that are not part of the optimal structure.

    ## What it does
    Identifies existing requires constraints that are not part of ANY view's optimal
    MST structure. These constraints can be safely removed as they don't contribute
    to query optimization.

    ## Why is this important?
    Unnecessary requires constraints can:
    - Create false ingestion dependencies
    - Make the data model harder to understand
    - Potentially cause issues if the constraint becomes invalid

    ## Example
    Container `Pump` has `requires: Tag`, but the optimal MST determined that
    `Pump → CogniteAsset` (which transitively covers Tag) is better.
    The `Pump → Tag` constraint can be removed.
    """

    code = f"{BASE_CODE}-002"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            containers_in_view = self.validation_resources.containers_by_view.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue

            user_containers = [c for c in containers_in_view if c.space not in COGNITE_SPACES]
            if not user_containers:
                continue

            _, to_remove = self.validation_resources.get_requires_changes_for_view(view_ref)

            for src, dst in to_remove:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' is mapping to container '{src!s}' that has a requires constraint to "
                            f"'{dst!s}' that is not part of any view's optimal structure. Consider removing this constraint."
                        ),
                        fix="Remove the unnecessary requires constraint",
                        code=self.code,
                    )
                )

        return recommendations


class UnresolvableQueryPerformance(DataModelValidator):
    """
    Identifies views with query performance issues that cannot be resolved with requires.

    ## What it does
    Detects views where no valid requires constraint solution exists:

    1. **CDF-only containers**: Views mapping only to CDF built-in containers.
       Since CDF containers cannot be modified, no requires can be added.

    2. **No valid solution**: The optimal MST structure doesn't create a connected
       hierarchy for this view (e.g., convergent edges pointing to a shared hub).

    ## Why is this important?
    These views will have suboptimal query performance that CANNOT be fixed by
    adding or removing requires constraints. The only solutions require restructuring:
    - Add a view-specific container that requires the others
    - Restructure the view to use different containers

    ## Example
    View `Test` maps to containers `Valve`, `InstrumentEquipment`, and `Tag`.
    The optimal constraints are `Valve → Tag` and `InstrumentEquipment → Tag`,
    but this creates a convergent structure where neither Valve nor InstrumentEquipment
    can reach each other. The view needs a new container or restructuring.
    """

    code = f"{BASE_CODE}-003"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            if view_ref.space in COGNITE_SPACES:
                continue

            containers_in_view = self.validation_resources.containers_by_view.get(view_ref, set())

            if len(containers_in_view) < 2:
                continue

            if self.validation_resources.forms_directed_path(
                containers_in_view, self.validation_resources.requires_constraint_graph
            ):
                continue

            user_containers = [c for c in containers_in_view if c.space not in COGNITE_SPACES]

            # Case 1: All containers are CDF built-in (not modifiable)
            if not user_containers:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                            "The view maps only to CDF built-in containers which cannot be modified to add requires constraints. "
                            "Consider adding a view-specific container (with at least one property) that requires the others."
                        ),
                        fix="Add a container (with at least one property) that requires the others, or restructure the view",
                        code=self.code,
                    )
                )
                continue

            # Case 2: MST algorithm couldn't find a valid solution
            to_add, _ = self.validation_resources.get_requires_changes_for_view(view_ref)

            if not to_add:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' is not optimized for querying which can lead to poor query performance. "
                            "No valid requires constraint solution was found, since the optimal configuration of constraints "
                            "do not create a connected hierarchy for this view's containers. "
                            "Consider adding a view-specific container (with at least one property) "
                            "that requires the others, or restructure the view."
                        ),
                        fix="Add a container (with at least one property) that requires the others, or restructure the view",
                        code=self.code,
                    )
                )

        return recommendations
