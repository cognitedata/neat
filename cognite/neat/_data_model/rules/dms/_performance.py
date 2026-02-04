"""Validators for checking performance-related aspects of the data model."""

from collections.abc import Iterable

from cognite.neat._data_model._analysis import RequiresChangeStatus, ResolvedReverseDirectRelation
from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model._fix_helpers import make_auto_constraint_id, make_auto_index_id
from cognite.neat._data_model.deployer.data_classes import AddedField, RemovedField, SeverityType
from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._data_types import DirectNodeRelation
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
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

    def _get_missing_constraints(self) -> Iterable[tuple[ViewReference, ContainerReference, ContainerReference]]:
        """Yields (view_ref, src, dst) for missing requires constraints."""
        for view_ref in self.validation_resources.merged.views:
            changes = self.validation_resources.get_requires_changes_for_view(view_ref)
            if changes.status != RequiresChangeStatus.CHANGES_AVAILABLE:
                continue
            for src, dst in changes.to_add:
                yield view_ref, src, dst

    def validate(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref, src, dst in self._get_missing_constraints():
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
                    "if you will be using this view to ingest instances, you will "
                    f"need to populate these instances into '{dst!s}' first"
                    + (f", for example through view '{view_example!s}'." if view_example else ".")
                )

            recommendations.append(
                Recommendation(
                    message=message,
                    fix="Add the recommended requires constraints to optimize query performance",
                    code=self.code,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to add missing requires constraints."""
        fix_actions: list[FixAction] = []
        seen: set[tuple[ContainerReference, ContainerReference]] = set()

        for _, src, dst in self._get_missing_constraints():
            if (src, dst) in seen:
                continue
            seen.add((src, dst))

            constraint_id = make_auto_constraint_id(dst)
            fix_actions.append(
                FixAction(
                    code=self.code,
                    resource_id=src,
                    changes=[
                        AddedField(
                            field_path=f"constraints.{constraint_id}",
                            new_value=RequiresConstraintDefinition(require=dst),
                            item_severity=SeverityType.WARNING,
                        )
                    ],
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

    def _get_suboptimal_constraints(self) -> Iterable[tuple[ViewReference, ContainerReference, ContainerReference]]:
        """Yields (view_ref, src, dst) for suboptimal requires constraints to remove."""
        for view_ref in self.validation_resources.merged.views:
            changes = self.validation_resources.get_requires_changes_for_view(view_ref)
            if changes.status != RequiresChangeStatus.CHANGES_AVAILABLE:
                continue
            for src, dst in changes.to_remove:
                yield view_ref, src, dst

    def validate(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref, src, dst in self._get_suboptimal_constraints():
            recommendations.append(
                Recommendation(
                    message=(
                        f"View '{view_ref!s}' is mapping to container '{src!s}' "
                        f"that has a requires constraint to '{dst!s}'. This constraint is "
                        "not part of the optimal structure. Consider removing it."
                    ),
                    fix="Remove suboptimal requires constraints",
                    code=self.code,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to remove suboptimal requires constraints."""
        fix_actions: list[FixAction] = []
        seen: set[tuple[ContainerReference, ContainerReference]] = set()

        for _, src, dst in self._get_suboptimal_constraints():
            if (src, dst) in seen:
                continue
            seen.add((src, dst))

            # Find auto-generated constraints to remove
            container = self.validation_resources.select_container(src)
            if not container:
                continue
            for constraint_id, constraint_def in self.validation_resources.get_requires_constraints(
                container, auto_only=True
            ):
                if constraint_def.require != dst:
                    continue
                fix_actions.append(
                    FixAction(
                        code=self.code,
                        resource_id=src,
                        changes=[
                            RemovedField(
                                field_path=f"constraints.{constraint_id}",
                                current_value=constraint_def,
                                item_severity=SeverityType.WARNING,
                            )
                        ],
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

        for resolved in self._get_missing_index_targets():
            recommendations.append(
                Recommendation(
                    message=(
                        f"View '{resolved.reverse_view_ref!s}' has a reverse direct relation "
                        f"'{resolved.reverse_property_id}' that cannot be efficently traversed through queries, "
                        f"since it points to container {resolved.container_ref!s}' "
                        f"property '{resolved.container_property_id}' that is unindexed. "
                    ),
                    fix="Add a cursorable B-tree index on the target direct relation property",
                    code=self.code,
                )
            )

        return recommendations

    def fix(self) -> list[FixAction]:
        """Return fix actions to add missing indexes."""
        fix_actions: list[FixAction] = []
        seen: set[tuple[ContainerReference, str]] = set()

        for resolved in self._get_missing_index_targets():
            key = (resolved.container_ref, resolved.container_property_id)
            if key in seen:
                continue
            seen.add(key)

            index_id = make_auto_index_id(resolved.container_property_id)
            fix_actions.append(
                FixAction(
                    code=self.code,
                    resource_id=resolved.container_ref,
                    changes=[
                        AddedField(
                            field_path=f"indexes.{index_id}",
                            new_value=BtreeIndex(properties=[resolved.container_property_id], cursorable=True),
                            item_severity=SeverityType.SAFE,
                        )
                    ],
                    message="Added index to enable efficient querying through reverse direct relations",
                )
            )

        return fix_actions

    def _get_missing_index_targets(self) -> list[ResolvedReverseDirectRelation]:
        """Get resolved reverse direct relations that are missing cursorable indexes."""
        targets = []

        for resolved in self.validation_resources.resolved_reverse_direct_relations:
            # Skip if container or container property couldn't be resolved
            if not resolved.container or not resolved.container_property:
                continue

            # Skip CDM containers - we can't modify these
            if resolved.container_ref.space in COGNITE_SPACES:
                continue

            # Must be a DirectNodeRelation type (other types handled by ReverseConnectionContainerPropertyWrongType)
            if not isinstance(resolved.container_property.type, DirectNodeRelation):
                continue

            # Skip if this is a list direct relation - indexes are not supported for list properties
            if resolved.container_property.type.list:
                continue

            # Skip if there's already a cursorable B-tree index on this property
            if resolved.container.indexes and any(
                isinstance(index, BtreeIndex)
                and index.cursorable
                and resolved.container_property_id in index.properties
                for index in resolved.container.indexes.values()
            ):
                continue

            targets.append(resolved)

        return targets
