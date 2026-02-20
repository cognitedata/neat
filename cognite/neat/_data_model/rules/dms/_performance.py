"""Validators for checking performance-related aspects of the data model."""

from cognite.neat._data_model._analysis import RequiresChangeStatus
from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model._fix import FixAction
from cognite.neat._data_model._identifiers import AutoIdentifier
from cognite.neat._data_model.deployer.data_classes import AddedField, ChangedField, RemovedField, SeverityType
from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-PERFORMANCE"


class MissingRequiresConstraint(DataModelRule):
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
    fixable = True

    def validate(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for (
            view_ref,
            source_container_ref,
            required_container_ref,
        ) in self.validation_resources.missing_requires_constraints:
            source_views = self.validation_resources.views_by_container.get(source_container_ref, set())
            other_views_using_source = source_views - {view_ref}
            views_impacted_by_change = self.validation_resources.find_views_mapping_to_containers(
                [source_container_ref, required_container_ref]
            )

            # Check if this is a "safe" recommendation (no cross-view dependencies)
            is_safe = not other_views_using_source or view_ref in views_impacted_by_change

            message = (
                f"View '{view_ref!s}' is not optimized for querying. "
                f"Add a 'requires' constraint from container '{source_container_ref!s}' "
                f"to '{required_container_ref!s}'."
            )
            if not is_safe:
                merged_views = set(self.validation_resources.merged.views)
                superset_views = views_impacted_by_change & merged_views
                view_example = min(superset_views, key=str) if superset_views else None
                message += (
                    " Note: this causes an ingestion dependency for this view, "
                    "if you will be using this view to ingest instances, you will "
                    f"need to populate these instances into '{required_container_ref!s}' first"
                    + (f", for example through view '{view_example!s}'." if view_example else ".")
                )

            recommendations.append(
                Recommendation(
                    message=message,
                    fix="Add the recommended requires constraints to optimize query performance",
                    code=self.code,
                    fixable=True,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to add missing requires constraints."""
        fix_actions: list[FixAction] = []
        # missing_requires_constraints yields (view, source, required) tuples,
        # so the same container pair can appear for multiple views. Dedup here
        # because each constraint only needs to be added once.
        seen: set[tuple[ContainerReference, ContainerReference]] = set()

        for (
            _,
            source_container_ref,
            required_container_ref,
        ) in self.validation_resources.missing_requires_constraints:
            if (source_container_ref, required_container_ref) in seen:
                continue
            seen.add((source_container_ref, required_container_ref))

            constraint_id = AutoIdentifier.for_constraint(required_container_ref)
            fix_actions.append(
                FixAction(
                    code=self.code,
                    resource_id=source_container_ref,
                    changes=(
                        AddedField(
                            field_path=f"constraints.{constraint_id}",
                            new_value=RequiresConstraintDefinition(require=required_container_ref),
                            item_severity=SeverityType.WARNING,
                        ),
                    ),
                    message="Added requires constraint to optimize query performance",
                )
            )

        return fix_actions


class SuboptimalRequiresConstraint(DataModelRule):
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
    fixable = True

    def validate(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for (
            view_ref,
            source_container_ref,
            required_container_ref,
        ) in self.validation_resources.suboptimal_requires_constraints:
            recommendations.append(
                Recommendation(
                    message=(
                        f"View '{view_ref!s}' is mapping to container '{source_container_ref!s}' "
                        f"that has a requires constraint to '{required_container_ref!s}'. This constraint is "
                        "not part of the optimal structure. Consider removing it."
                    ),
                    fix="Remove suboptimal requires constraints",
                    code=self.code,
                    fixable=True,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to remove suboptimal requires constraints."""
        fix_actions: list[FixAction] = []
        # suboptimal_requires_constraints yields (view, source, required) tuples,
        # so the same container pair can appear for multiple views. Dedup here
        # because each constraint only needs to be removed once.
        seen: set[tuple[ContainerReference, ContainerReference]] = set()

        for (
            _,
            source_container_ref,
            required_container_ref,
        ) in self.validation_resources.suboptimal_requires_constraints:
            if (source_container_ref, required_container_ref) in seen:
                continue
            seen.add((source_container_ref, required_container_ref))

            # validate() only needs the references for the message, but fix() needs
            # the actual container to resolve the constraint ID for the FixAction.
            container = self.validation_resources.select_container(source_container_ref)
            if not container:
                continue
            for constraint_id, constraint_def in self.validation_resources.get_requires_constraints(
                container, auto_only=True
            ):
                if constraint_def.require != required_container_ref:
                    continue
                fix_actions.append(
                    FixAction(
                        code=self.code,
                        resource_id=source_container_ref,
                        changes=(
                            RemovedField(
                                field_path=f"constraints.{constraint_id}",
                                current_value=constraint_def,
                                item_severity=SeverityType.WARNING,
                            ),
                        ),
                        message="Removed suboptimal requires constraint",
                    )
                )

        return fix_actions


class UnresolvableQueryPerformance(DataModelRule):
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

    def validate(self) -> list[Recommendation]:
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


class MissingReverseDirectRelationTargetIndex(DataModelRule):
    """
    Recommends adding a cursorable index on direct relation properties that are
    targets of reverse direct relations for query performance.

    ## What it does
    Identifies direct relation properties that are referenced by reverse direct relations
    but lack a cursorable B-tree index. When querying through a reverse direct relation,
    CDF needs to look up nodes that have the direct relation pointing to the
    source nodes. Without an index, this requires scanning many nodes inefficiently.

    ## Why is this important?
    Traversing a reverse direct relation (inwards direction) requires an index on the
    target direct relation property. Without this index, queries will be inefficient,
    potentially leading to timeouts over time, as they won't scale well with data volume.

    The exception is when the target direct relation is a list property. In that case,
    this validator will not flag them, as reverse direct relations targeting lists of
    direct relations needs to be traversed using the `instances/search` endpoint instead,
    which does not directly benefit from adding indexes to container properties.

    ## Example
    View `WindFarm` has a reverse property `turbines` through `WindTurbine.windFarm`.
    Container `WindTurbine` should have a cursorable B-tree index on the `windFarm`
    property to enable efficient traversal from WindFarm to its turbines.
    """

    code = f"{BASE_CODE}-004"
    issue_type = Recommendation
    alpha = True
    fixable = True

    def validate(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for resolved_reverse_direct_relation, _ in self.validation_resources.missing_reverse_relation_index_targets:
            recommendations.append(
                Recommendation(
                    message=(
                        f"View '{resolved_reverse_direct_relation.reverse_view_ref!s}' has a reverse direct relation "
                        f"'{resolved_reverse_direct_relation.reverse_property_id}' that cannot be efficiently "
                        f"traversed through queries, "
                        f"since it points to container {resolved_reverse_direct_relation.container_ref!s}' "
                        f"property '{resolved_reverse_direct_relation.container_property_id}' that is unindexed. "
                    ),
                    fix="Add a cursorable B-tree index on the target direct relation property",
                    code=self.code,
                    fixable=True,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to add or update indexes."""
        fix_actions: list[FixAction] = []
        # missing_reverse_relation_index_targets yields per-view results,
        # so the same container/property pair can appear for multiple views.
        # Dedup here because each index only needs to be added/updated once.
        seen: set[tuple[ContainerReference, str]] = set()

        for (
            resolved_reverse_direct_relation,
            existing_index,
        ) in self.validation_resources.missing_reverse_relation_index_targets:
            key = (
                resolved_reverse_direct_relation.container_ref,
                resolved_reverse_direct_relation.container_property_id,
            )
            if key in seen:
                continue
            seen.add(key)

            if existing_index:
                index_id, current_index = existing_index
                change: AddedField | ChangedField = ChangedField(
                    field_path=f"indexes.{index_id}",
                    current_value=current_index,
                    new_value=BtreeIndex(
                        properties=current_index.properties, by_space=current_index.by_space, cursorable=True
                    ),
                    item_severity=SeverityType.SAFE,
                )
                message = "Updated index to be cursorable for efficient reverse relation queries"
            else:
                index_id = AutoIdentifier.for_index(resolved_reverse_direct_relation.container_property_id)
                change = AddedField(
                    field_path=f"indexes.{index_id}",
                    new_value=BtreeIndex(
                        properties=[resolved_reverse_direct_relation.container_property_id], cursorable=True
                    ),
                    item_severity=SeverityType.SAFE,
                )
                message = "Added cursorable index for efficient reverse direct relation queries"

            fix_actions.append(
                FixAction(
                    code=self.code,
                    resource_id=resolved_reverse_direct_relation.container_ref,
                    changes=(change,),
                    message=message,
                )
            )

        return fix_actions
