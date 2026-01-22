"""Validators for checking performance-related aspects of the data model.

This module contains validators that check for query performance issues related to
container requires constraints:

- MissingRequiresConstraint: Add constraints to optimize query performance
- SuboptimalRequiresConstraint: Remove constraints not in the optimal structure
- UnresolvableQueryPerformance: Structural issues that can't be solved with requires
"""

from cognite.neat._data_model._analysis import RequiresChangeStatus
from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.models.dms import ViewReference
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-PERFORMANCE"


class MissingRequiresConstraint(DataModelValidator):
    """
    Recommends adding requires constraints to optimize query performance.

    ## What it does
    Identifies views that is mapping to containers where adding a requires constraint,
    would improve query performance. The recommendation message indicates whether the
    change is "safe" or requires attention to potential ingestion dependencies.

    ## Why is this important?
    Views without proper requires constraints may have poor query performance.
    Adding requires constraints enables queries to perform under-the-hood optimizations.

    ## Example
    View `Valve` is mapping to both containers `Valve` and `CogniteEquipment`.
    A `requires` constraint from `Valve` to `CogniteEquipment` is likely needed
    to enable efficient query performance.
    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            changes = self.validation_resources.get_requires_changes_for_view(view_ref)

            if changes.status != RequiresChangeStatus.CHANGES_AVAILABLE:
                continue

            for src, dst in changes.to_add:
                src_views = self.validation_resources.views_by_container.get(src, set())
                other_views_with_src = src_views - {view_ref}
                views_impacted_by_change = self.validation_resources.find_views_mapping_to_containers([src, dst])

                # Check if this is a "safe" recommendation (no cross-view dependencies)
                is_safe = not other_views_with_src or view_ref in views_impacted_by_change

                if is_safe:
                    message = (
                        f"View '{view_ref!s}' is not optimized for querying. "
                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}'."
                    )
                else:
                    # Find a view to suggest: prefer one mapping to both, fallback to one mapping to dst
                    merged_views = set(self.validation_resources.merged.views)
                    merged_views_mapping_to_both = views_impacted_by_change & merged_views
                    view_example: ViewReference | None = None
                    if merged_views_mapping_to_both:
                        view_example = min(merged_views_mapping_to_both, key=str)
                    else:
                        dst_views = self.validation_resources.views_by_container.get(dst, set()) & merged_views
                        if dst_views:
                            view_example = min(dst_views, key=str)

                    message = (
                        f"View '{view_ref!s}' is not optimized for querying. "
                        f"Add a 'requires' constraint from '{src!s}' to '{dst!s}'. "
                        "Note: this causes an ingestion dependency for this view, "
                        "if you will be using it to ingest instances, you will "
                        f"need to populate these instances into '{dst!s}' "
                        + (f"first, for example through view '{view_example!s}'." if view_example else "first.")
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
    Recommends removing requires constraints that are not part of the structure
    considered optimal for query performance by Neat.

    ## What it does
    Identifies existing requires constraints that are not optimal. These constraints
    can be safely removed as they don't contribute to query optimization when all other
    optimal constraints are applied.

    ## Why is this important?
    Unnecessary requires constraints can:
    - Create unnecessary ingestion dependencies
    - Cause invalid requires constraint cycles if optimal constraints are applied

    ## Example
    Container `Tag` has a `requires` constraint to `Pump`, but NEAT determined that
    `Pump → Tag` is more optimal. The existing `Tag → Pump` constraint should then
    be removed when applying all optimal constraints.
    """

    code = f"{BASE_CODE}-002"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            changes = self.validation_resources.get_requires_changes_for_view(view_ref)

            if changes.status != RequiresChangeStatus.CHANGES_AVAILABLE:
                continue

            for src, dst in changes.to_remove:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' has a requires constraint '{src!s}' -> '{dst!s}' "
                            "that is not part of the optimal structure. Consider removing it."
                        ),
                        fix="Remove the unnecessary requires constraint",
                        code=self.code,
                    )
                )

        return recommendations


class UnresolvableQueryPerformance(DataModelValidator):
    """
    Identifies views with query performance issues that cannot be resolved.
    This is likely to be caused by unintended modeling choices.

    ## What it does
    Detects views where no valid requires constraint solution exists:

    1. **View maps only to CDF built-in containers**:
       Since CDF containers cannot be modified, no requires can be added.

    2. **No valid solution**:
       This view is causing issues when optimizing requires constraints
       for other views, due to its structure (mapping non-overlapping containers)

    ## Why is this important?
    These views will have suboptimal query performance that CANNOT be fixed by
    adding or removing requires constraints. The only solutions require restructuring:
    - Add a view-specific container that requires all the other containers in the view
    - Restructure the view to use different containers

    ## Example
    View `MultipleEquipments` maps only to containers `Valve` and `InstrumentEquipment`.
    The optimal constraints are `Valve → CogniteEquipment` and `InstrumentEquipment → CogniteEquipment`
    due to other views needing these constraints to optimize their query performance.
    This means however, that neither Valve nor InstrumentEquipment can reach each other without
    creating complex ingestion dependencies. The view needs a new container or restructuring.
    """

    code = f"{BASE_CODE}-003"
    issue_type = Recommendation
    alpha = True

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged.views:
            if view_ref.space in COGNITE_SPACES:
                continue

            changes = self.validation_resources.get_requires_changes_for_view(view_ref)

            if changes.status == RequiresChangeStatus.NO_MODIFIABLE_CONTAINERS:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' has poor query performance. "
                            "It maps only to CDF built-in containers which cannot have requires constraints. "
                            "Consider adding a view-specific container that requires the others."
                        ),
                        fix="Add a container that requires the others, or restructure the view",
                        code=self.code,
                    )
                )
            elif changes.status == RequiresChangeStatus.UNSOLVABLE:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' has poor query performance. "
                            "No valid requires constraint solution was found. "
                            "Consider adding a view-specific container that requires the others."
                        ),
                        fix="Add a container that requires the others, or restructure the view",
                        code=self.code,
                    )
                )

        return recommendations
