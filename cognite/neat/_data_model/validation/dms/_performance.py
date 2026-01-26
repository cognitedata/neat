"""Validators for checking performance-related aspects of the data model."""

from cognite.neat._data_model._analysis import RequiresChangeStatus
from cognite.neat._data_model._constants import COGNITE_SPACES
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

                message = (
                    f"View '{view_ref!s}' is not optimized for querying. "
                    f"Add a 'requires' constraint from the container '{src!s}' to '{dst!s}'."
                )
                if not is_safe:
                    # Find a superset view to suggest for ingestion
                    merged_views = set(self.validation_resources.merged.views)
                    superset_views = views_impacted_by_change & merged_views
                    view_example = min(superset_views, key=str) if superset_views else None
                    message += (
                        " Note: this causes an ingestion dependency for this view, "
                        " if you will be using this view to ingest instances, you will "
                        f"need to populate these instances into '{dst!s}' first"
                        + (f", for example through view '{view_example!s}'." if view_example else ".")
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
    Recommends removing requires constraints that are not optimal.

    ## What it does
    Identifies existing requires constraints that are not optimal for querying purposes,
    as they are either redundant or create unnecessary ingestion dependencies when all
    other optimal constraints are applied. These constraints can be safely removed
    without affecting query performance.

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
                            f"View '{view_ref!s}' is mapping to container '{src!s}' "
                            f"that has a requires constraint to '{dst!s}'. This constraint is "
                            "not part of the optimal structure. Consider removing it."
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
                            f"View '{view_ref!s}' is not optimized for querying. It maps only to CDF "
                            "built-in containers and some of these lack requires constraints between them. "
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
                            f"View '{view_ref!s}' is not optimized for querying. "
                            "No valid requires constraint solution was found. "
                            "Consider adding a view-specific container that requires the others."
                        ),
                        fix="Add a container that requires the others, or restructure the view",
                        code=self.code,
                    )
                )

        return recommendations
