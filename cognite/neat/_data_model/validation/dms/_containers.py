"""Validators for checking containers in the data model."""

from typing import cast

from cognite.neat._data_model.models.dms._constraints import Constraint, RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

BASE_CODE = "NEAT-DMS-CONTAINER"


class ExternalContainerDoesNotExist(DataModelValidator):
    """
    Validates that any container referenced by a view property, when the
    referenced container does not belong to the data model's space, exists in CDF.

    ## What it does
    For each view property that maps to a container in a different space than the data model,
    this validator checks that the referenced external container exists in CDF.

    ## Why is this bad?
    If a view property references a container that does not exist in CDF,
    the data model cannot be deployed. The affected view property will not function, and the
    deployment of the entire data model will fail.

    ## Example
    View `my_space:WindTurbine` has a property `location` that maps to container
    `other_space:WindTurbineContainer`, where `other_space` differs from `my_space`. If that
    container does not exist in CDF, the model cannot be deployed.
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
                    f"ImplementedViewNotExisting.run: View {view_ref!s} "
                    "not found in local resources. This is a bug in NEAT."
                )

            if view.properties is None:
                continue

            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                if property_.container.space == self.validation_resources.merged_data_model.space:
                    continue

                # Check existence of container in CDF
                if property_.container not in self.validation_resources.cdf.containers:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} maps to "
                                f"external container {property_.container!s} which does not exist in CDF."
                            ),
                            fix="Define necessary container in CDF",
                            code=self.code,
                        )
                    )

        return errors


class ExternalContainerPropertyDoesNotExist(DataModelValidator):
    """
    Validates that any container property referenced by a view property, when the
    referenced container does not belong to the data model's space, exists in CDF.

    ## What it does
    For each view property that maps to a container in a different space than the data model,
    this validator checks that the referenced container property exists in that external container in CDF.
    This validator only runs if the external container exists in CDF.

    ## Why is this bad?
    If a view property references a container property that does not exist in CDF,
    the data model cannot be deployed. The affected view property will not function, and the
    deployment of the entire data model will fail.

    ## Example
    View `my_space:WindTurbine` has a property `location` that maps to container property
    `gpsCoordinates` in `other_space:WindTurbineContainer`. If `gpsCoordinates` does not exist
    in that container in CDF, deployment will fail.
    """

    code = f"{BASE_CODE}-002"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if self.validation_resources.merged_data_model.views:
            for view_ref in self.validation_resources.merged_data_model.views:
                view = self.validation_resources.select_view(view_ref)

                if not view:
                    raise RuntimeError(
                        f"ImplementedViewNotExisting.run: View {view_ref!s} "
                        "not found in local resources. This is a bug in NEAT."
                    )

                if view.properties is None:
                    continue

                for property_ref, property_ in view.properties.items():
                    if not isinstance(property_, ViewCorePropertyRequest):
                        continue

                    if property_.container.space == self.validation_resources.merged_data_model.space:
                        continue

                    # Only check property if container exists in CDF
                    # this check is done in ExternalContainerDoesNotExist
                    if property_.container not in self.validation_resources.cdf.containers:
                        continue

                    # Check existence of container property in CDF
                    if (
                        property_.container_property_identifier
                        not in self.validation_resources.cdf.containers[property_.container].properties
                    ):
                        errors.append(
                            ConsistencyError(
                                message=(
                                    f"View {view_ref!s} property {property_ref!s} maps to "
                                    f"external container {property_.container!s} which does not have "
                                    f"property '{property_.container_property_identifier}' in CDF."
                                ),
                                fix="Define necessary container property in CDF",
                                code=self.code,
                            )
                        )

        return errors


class RequiredContainerDoesNotExist(DataModelValidator):
    """
    Validates that any container required by another container exists in the data model.

    ## What it does
    For each container in the data model, this validator checks that any container it
    requires (via requires constraints) exists either in the data model or in CDF.

    ## Why is this bad?
    If a container requires another container that does not exist in the data model or in CDF,
    the data model cannot be deployed. The affected container will not function, and
    the deployment of the entire data model will fail.

    ## Example
    Container `windy_space:WindTurbineContainer` has a constraint requiring `windy_space:LocationContainer`.
    If `windy_space:LocationContainer` does not exist in the data model or in CDF, deployment will fail.
    """

    code = f"{BASE_CODE}-003"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for container_ref, container in self.validation_resources.merged.containers.items():
            if not container.constraints:
                continue

            for constraint_ref, constraint in cast(dict[str, Constraint], container.constraints).items():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                if not self.validation_resources.select_container(constraint.require):
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"Container '{container_ref!s}' constraint '{constraint_ref}' requires container "
                                f"'{constraint.require!s}' which does not exist."
                            ),
                            fix="Define necessary container in the data model",
                            code=self.code,
                        )
                    )

        return errors


class MissingRequiresConstraint(DataModelValidator):
    """
    Validates that containers used together in views have appropriate requires constraints.

    ## What it does
    For views that map to multiple containers, this validator checks that the containers
    have appropriate "requires" constraints on each other. If container A only ever appears
    together with container B (never without B), then A should have a requires constraint on B.

    The requires constraint is transitive: if A requires B and B requires C, then A
    transitively requires C. In this case, A does not need a direct constraint on C.

    ## Why is this bad?
    When fetching data for a view without any filters specified, the API defaults to applying
    a `hasData` filter on all mapped containers. With proper requires constraints in place,
    the `hasData` check can be reduced to be only the container containing data specific to this view.
    For example, if a view maps to `CogniteAsset` container, and `CogniteAsset` requires `CogniteVisualizable`,
    `CogniteDescribable`, and `CogniteSourceable`, then `hasData` only needs to check `CogniteAsset` container presence.

    Without requires constraints, multiple `hasData` filters are generated which trigger
    many database joins. This becomes expensive and slow, especially for views that map
    to several containers.

    ## Example
    View `CogniteAsset` maps to containers `CogniteAsset`, `CogniteVisualizable`,
    `CogniteDescribable`, and `CogniteSourceable`. The `CogniteAsset` container should have requires
    constraints on all other containers. This allows queries to use a `hasData` filter with only
    the `CogniteAsset` container.
    """

    code = f"{BASE_CODE}-004"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        # For each local container, check if it should require other containers
        for container_a in self.validation_resources.local.containers:
            if container_a.space != self.validation_resources.merged_data_model.space:
                continue
            views_with_a = self.validation_resources.container_to_views.get(container_a, set())
            if not views_with_a:
                continue  # Container not used in any view

            # Find all containers that appear with A in any view
            containers_with_a: set[ContainerReference] = set()
            for view_ref in views_with_a:
                containers_with_a.update(self.validation_resources.view_to_containers.get(view_ref, set()))
            containers_with_a.discard(container_a)

            # Get what A already transitively requires
            transitively_required = self.validation_resources.get_transitively_required_containers(container_a)

            # Collect containers that A always appears with (strongest recommendation)
            always_required: set[ContainerReference] = set()

            for container_b in containers_with_a:
                # Skip if A already transitively requires B
                if container_b in transitively_required:
                    continue

                views_with_b = self.validation_resources.container_to_views.get(container_b, set())

                # Check if A always appears with B (A never appears without B)
                if views_with_a <= views_with_b:
                    # Check if there's a container C that A already requires, and C also always appears with B
                    # but C doesn't require B. If so, the proper recommendation is for C to require B, not A.
                    should_skip = any(
                        self.validation_resources.container_to_views.get(c, set()) <= views_with_b
                        and container_b not in self.validation_resources.get_transitively_required_containers(c)
                        for c in transitively_required
                    )
                    if not should_skip:
                        always_required.add(container_b)

            # Find the minimal set of constraints needed
            minimal_always = self.validation_resources.find_minimal_requires_set(always_required)

            # Find containers that A appears with in some views but not all
            # Include if: views without B are all single-container, OR B transitively covers always_required
            partial_overlap: set[ContainerReference] = set()
            for container_b in containers_with_a:
                if container_b in transitively_required or container_b in always_required:
                    continue

                views_with_b = self.validation_resources.container_to_views.get(container_b, set())
                views_without_b = views_with_a - views_with_b
                if not views_without_b:
                    continue  # A always appears with B - handled above

                # Include if B transitively covers something in always_required
                if self.validation_resources.get_transitively_required_containers(container_b) & always_required:
                    partial_overlap.add(container_b)
                    continue

                # Include if views where A appears without B are all single-container views
                all_single_container = all(
                    len(self.validation_resources.view_to_containers.get(v, set())) == 1 for v in views_without_b
                )
                if all_single_container:
                    partial_overlap.add(container_b)

            minimal_partial = self.validation_resources.find_minimal_requires_set(
                partial_overlap, already_covered_by=always_required
            )

            for container_b in minimal_always:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' is always used together with container "
                            f"'{container_b!s}' in views, but does not have a requires constraint on it. "
                            "This can cause suboptimal performance when querying instances through these views."
                        ),
                        fix="Add a requires constraint between the containers",
                        code=self.code,
                    )
                )

            # Recommend partial overlap containers with contextual details
            for container_b in minimal_partial:
                views_with_b = self.validation_resources.container_to_views.get(container_b, set())
                views_with_both = views_with_a & views_with_b
                views_without_b = views_with_a - views_with_b

                views_with_both_str = ", ".join(sorted(str(v) for v in views_with_both))
                views_without_b_str = ", ".join(sorted(str(v) for v in views_without_b))

                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' appears with container '{container_b!s}' "
                            f"in views: [{views_with_both_str}], but not in: [{views_without_b_str}]. "
                            f"Adding a requires constraint in '{container_a!s}' on '{container_b!s}' "
                            f"would improve query performance for these views, but may complicate "
                            f"ingestion for views where '{container_a!s}' appears without '{container_b!s}'."
                        ),
                        fix=(
                            "Consider adding a requires constraint if query performance "
                            "is more important than ingestion flexibility"
                        ),
                        code=self.code,
                    )
                )

        return recommendations


class UnnecessaryRequiresConstraint(DataModelValidator):
    """
    Validates that requires constraints between containers are meaningful.

    ## What it does
    For each container with a requires constraint, this validator checks whether the
    required container ever appears together with the requiring container in any view.
    If they never appear together, the requires constraint will not have any performance benefit.
    Requires constraints could still be useful for consistency checks however.

    ## Why is this bad?
    A requires constraint means that the required container must be populated before
    the requiring container can be used. If these containers never appear together in
    any view, this constraint creates an unnecessary dependency - the required container
    must be populated first, even though it's not used alongside the requiring container.

    ## Example
    Container `my_space:OrderContainer` has a requires constraint on `my_space:CustomerContainer`.
    However, no view maps to both containers. This means `CustomerContainer` must be populated
    before `OrderContainer` can be used, even though they serve independent views.
    """

    code = f"{BASE_CODE}-005"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        # Check each local container's requires constraints
        for container_ref, container in self.validation_resources.local.containers.items():
            if not container.constraints:
                continue

            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                if constraint.require not in self.validation_resources.merged.containers:
                    continue  # Handled by RequiredContainerDoesNotExist

                if self.validation_resources.containers_are_mapped_together(container_ref, constraint.require):
                    continue  # They appear together, constraint is useful

                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_ref!s}' has a requires constraint on "
                            f"'{constraint.require!s}', but they never appear together in any view. "
                            f"This creates an unnecessary dependency and does not provide any performance benefit."
                        ),
                        fix="Remove the requires constraint if these containers are meant to be used independently",
                        code=self.code,
                    )
                )

        return recommendations


class RequiresConstraintCycle(DataModelValidator):
    """
    Validates that requires constraints between containers do not form cycles.

    ## What it does
    This validator checks if the requires constraints between containers form a cycle.
    For example, if container A requires B, B requires C, and C requires A, this forms
    a cycle.

    ## Why is this bad?
    Cycles in requires constraints will be rejected by the CDF API. The deployment
    of the data model will fail if any such cycle exists.

    ## Example
    Container `my_space:OrderContainer` requires `my_space:CustomerContainer`, which
    requires `my_space:OrderContainer`. This creates a cycle and will be rejected.
    """

    code = f"{BASE_CODE}-006"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        # Track which containers we've already reported cycles for
        reported_cycles: set[frozenset[ContainerReference]] = set()

        # Check each local container for cycles
        for container_ref in self.validation_resources.local.containers:
            cycle = self.validation_resources.find_requires_constraint_cycle(container_ref, container_ref)
            if not cycle:
                continue
            # Create a frozenset of the cycle to avoid reporting the same cycle multiple times
            cycle_set = frozenset(cycle[:-1])  # Exclude the duplicate end element
            if cycle_set in reported_cycles:
                continue
            reported_cycles.add(cycle_set)
            cycle_str = " -> ".join(str(c) for c in cycle)
            errors.append(
                ConsistencyError(
                    message=f"Requires constraints form a cycle: {cycle_str}",
                    fix="Remove one of the requires constraints to break the cycle",
                    code=self.code,
                )
            )

        return errors
