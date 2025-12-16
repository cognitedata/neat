"""Validators for checking containers in the data model."""

from typing import cast

from cognite.neat._data_model.models.dms._constraints import Constraint, RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

BASE_CODE = "NEAT-DMS-CONTAINER"


def _build_container_to_views_mapping(
    views_by_reference: dict[ViewReference, ViewRequest],
) -> tuple[dict[str, set[str]], dict[str, ContainerReference]]:
    """Build a mapping from container reference strings to the views that use them.

    Returns:
        A tuple of:
        - container_to_views: mapping from container string to set of view strings
        - str_to_container: mapping from container string back to ContainerReference
    """
    container_to_views: dict[str, set[str]] = {}
    str_to_container: dict[str, ContainerReference] = {}
    for view_ref, view in views_by_reference.items():
        if not view.properties:
            continue
        for property_ in view.properties.values():
            if isinstance(property_, ViewCorePropertyRequest):
                container_ref = property_.container
                container_str = str(container_ref)
                if container_str not in container_to_views:
                    container_to_views[container_str] = set()
                    str_to_container[container_str] = container_ref
                container_to_views[container_str].add(str(view_ref))
    return container_to_views, str_to_container


def _get_direct_required_containers(
    container_ref: ContainerReference,
    containers_by_reference: dict[ContainerReference, ContainerRequest],
) -> set[ContainerReference]:
    """Get all containers that a container directly requires."""
    # Use string comparison to find the container (avoids object identity issues)
    container_str = str(container_ref)
    container: ContainerRequest | None = None
    for ref, cont in containers_by_reference.items():
        if str(ref) == container_str:
            container = cont
            break

    if not container or not container.constraints:
        return set()

    required: set[ContainerReference] = set()
    for constraint in container.constraints.values():
        if isinstance(constraint, RequiresConstraintDefinition):
            required.add(constraint.require)
    return required


def _get_transitively_required_containers(
    container_ref: ContainerReference,
    containers_by_reference: dict[ContainerReference, ContainerRequest],
    visited: set[str] | None = None,
) -> set[ContainerReference]:
    """Get all containers that a container requires (transitively)."""
    if visited is None:
        visited = set()
    container_str = str(container_ref)
    if container_str in visited:
        return set()
    visited.add(container_str)

    direct_required = _get_direct_required_containers(container_ref, containers_by_reference)
    all_required = direct_required.copy()
    for req in direct_required:
        all_required.update(_get_transitively_required_containers(req, containers_by_reference, visited))
    return all_required


def _build_view_to_containers_mapping(
    views_by_reference: dict[ViewReference, ViewRequest],
) -> dict[str, set[ContainerReference]]:
    """Build a mapping from view references (as strings) to the containers they use."""
    view_to_containers: dict[str, set[ContainerReference]] = {}
    for view_ref, view in views_by_reference.items():
        if not view.properties:
            continue
        containers: set[ContainerReference] = set()
        for property_ in view.properties.values():
            if isinstance(property_, ViewCorePropertyRequest):
                containers.add(property_.container)
        if containers:
            view_to_containers[str(view_ref)] = containers
    return view_to_containers


def _find_requires_constraint_cycle(
    start: ContainerReference,
    current: ContainerReference,
    containers_by_reference: dict[ContainerReference, ContainerRequest],
    visited: set[str] | None = None,
    path: list[ContainerReference] | None = None,
) -> list[ContainerReference] | None:
    """Find a cycle in requires constraints starting from 'start' through 'current'.

    Returns the cycle path if found, None otherwise.
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []

    current_str = str(current)
    if current_str in visited:
        if str(start) == current_str:
            return path + [current]
        return None

    visited.add(current_str)
    path.append(current)

    for required in _get_direct_required_containers(current, containers_by_reference):
        cycle = _find_requires_constraint_cycle(start, required, containers_by_reference, visited, path)
        if cycle:
            return cycle

    path.pop()
    return None


def _is_covered_by_any(
    container: ContainerReference,
    container_set: set[ContainerReference],
    containers_by_reference: dict[ContainerReference, ContainerRequest],
    exclude: ContainerReference | None = None,
) -> bool:
    """Check if container is transitively covered by any container in the set.

    Args:
        container: The container to check coverage for
        container_set: Set of containers that might cover the target
        containers_by_reference: Container lookup dictionary
        exclude: Optionally exclude a specific container from consideration
    """
    for other in container_set:
        if exclude is not None and other == exclude:
            continue
        if container in _get_transitively_required_containers(other, containers_by_reference):
            return True
    return False


def _find_minimal_set(
    candidates: set[ContainerReference],
    containers_by_reference: dict[ContainerReference, ContainerRequest],
    already_covered_by: set[ContainerReference] | None = None,
) -> set[ContainerReference]:
    """Find the minimal set of containers needed (removing those transitively covered by others).

    Args:
        candidates: Set of candidate containers
        containers_by_reference: Container lookup dictionary
        already_covered_by: Containers that already provide coverage (to filter out candidates)
    """
    if already_covered_by is None:
        already_covered_by = set()

    minimal: set[ContainerReference] = set()
    for container in candidates:
        # Skip if already covered by the pre-existing set
        if _is_covered_by_any(container, already_covered_by, containers_by_reference):
            continue
        # Skip if covered by another container in the same candidates set
        if _is_covered_by_any(container, candidates, containers_by_reference, exclude=container):
            continue
        minimal.add(container)
    return minimal


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
    View `my_space:CogniteAsset` maps to containers `CogniteAsset`, `CogniteVisualizable`,
    `CogniteDescribable`, and `CogniteSourceable`. The `CogniteAsset` container should have requires
    constraints on all other containers. This allows queries to use a `hasData` filter with only the `CogniteAsset` container.
    """

    code = f"{BASE_CODE}-004"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        merged_views = self.validation_resources.merged.views
        merged_containers = self.validation_resources.merged.containers
        local_containers = self.validation_resources.local.containers
        model_space = self.validation_resources.merged_data_model.space

        # Use cached container_to_views from ValidationResources
        container_to_views = self.validation_resources.container_to_views

        # Build str_to_container mapping for looking up ContainerReference from string
        _, str_to_container = _build_container_to_views_mapping(merged_views)
        view_to_containers = _build_view_to_containers_mapping(merged_views)

        # For each local container, check if it should require other containers
        for container_a_str, views_with_a in container_to_views.items():
            container_a = str_to_container[container_a_str]
            # Only check local containers
            if container_a.space != model_space:
                continue
            if container_a not in local_containers:
                continue

            # Find all containers that appear with A in any view
            containers_with_a: set[ContainerReference] = set()
            for view_str in views_with_a:
                containers_with_a.update(view_to_containers.get(view_str, set()))
            containers_with_a.discard(container_a)

            # Get what A already transitively requires
            transitively_required = _get_transitively_required_containers(container_a, merged_containers)

            # Collect containers that A always appears with (strongest recommendation)
            always_required: set[ContainerReference] = set()

            for container_b in containers_with_a:
                # Skip if A already transitively requires B
                if container_b in transitively_required:
                    continue

                views_with_b = container_to_views.get(str(container_b), set())

                # Check if A always appears with B (A never appears without B)
                if views_with_a <= views_with_b:
                    # Check if there's a container C that A already requires, and C also always appears with B
                    # but C doesn't require B. If so, the proper recommendation is for C to require B, not A.
                    should_skip = any(
                        container_to_views.get(str(c), set()) <= views_with_b
                        and container_b not in _get_transitively_required_containers(c, merged_containers)
                        for c in transitively_required
                    )
                    if not should_skip:
                        always_required.add(container_b)

            # Find the minimal set of constraints needed
            minimal_always = _find_minimal_set(always_required, merged_containers)

            # Find containers that A appears with in some views but not all (optional constraints)
            # Include if: views without B are all single-container, OR B transitively covers always_required
            partial_overlap: set[ContainerReference] = set()
            for container_b in containers_with_a:
                if container_b in transitively_required or container_b in always_required:
                    continue

                views_with_b = container_to_views.get(str(container_b), set())
                views_without_b = views_with_a - views_with_b
                if not views_without_b:
                    continue  # A always appears with B - handled above

                # Include if B transitively covers something in always_required
                if _get_transitively_required_containers(container_b, merged_containers) & always_required:
                    partial_overlap.add(container_b)
                    continue

                # Include if views where A appears without B are all single-container views
                all_single_container = all(len(view_to_containers.get(v, set())) == 1 for v in views_without_b)
                if all_single_container:
                    partial_overlap.add(container_b)

            minimal_partial = _find_minimal_set(partial_overlap, merged_containers, already_covered_by=always_required)

            for container_b in minimal_always:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' is always used together with container "
                            f"'{container_b!s}' but does not have a requires constraint on it."
                        ),
                        fix="Add a requires constraint between the containers",
                        code=self.code,
                    )
                )

            # Recommend partial overlap containers with contextual details
            for container_b in minimal_partial:
                views_with_b = container_to_views.get(str(container_b), set())
                views_with_both = views_with_a & views_with_b
                views_without_b = views_with_a - views_with_b

                views_with_both_str = ", ".join(sorted(views_with_both))
                views_without_b_str = ", ".join(sorted(views_without_b))

                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' appears with container '{container_b!s}' "
                            f"in views: [{views_with_both_str}], but not in: [{views_without_b_str}]. "
                            f"Adding a requires constraint in '{container_a!s}' on '{container_b!s}' would improve query performance for these views, "
                            f"but may complicate ingestion for views where '{container_a!s}' appears without '{container_b!s}'."
                        ),
                        fix="Consider adding a requires constraint if query performance is more important than ingestion flexibility",
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

        local_containers = self.validation_resources.local.containers
        merged_containers = self.validation_resources.merged.containers

        # Check each local container's requires constraints
        for container_ref, container in local_containers.items():
            if not container.constraints:
                continue

            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                if constraint.require not in merged_containers:
                    continue  # Handled by RequiredContainerDoesNotExist

                if self.validation_resources.containers_appear_together(container_ref, constraint.require):
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

        local_containers = self.validation_resources.local.containers
        merged_containers = self.validation_resources.merged.containers

        # Track which containers we've already reported cycles for
        reported_cycles: set[frozenset[ContainerReference]] = set()

        # Check each local container for cycles
        for container_ref in local_containers:
            cycle = _find_requires_constraint_cycle(container_ref, container_ref, merged_containers)
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


class RequiresConstraintComplicatesIngestion(DataModelValidator):
    """
    Validates that containers with requires constraints can be populated together in at least one view.

    ## What it does
    For each container A that has a requires constraint on container B, this validator checks
    whether there exists at least one view that maps to both container A AND all non-nullable
    properties of container B.

    ## Why is this bad?
    If container A requires container B, but no view maps to both A and all non-nullable properties
    of B, then ingestion becomes more complex:
    - Container B must be populated FIRST (before A can be used, due to the requires constraint)
    - The non-nullable properties of B must be provided during this initial population
    - There's no way to populate both containers in a single view-based ingestion

    This forces a two-step ingestion process and may require using the containers API directly
    for the initial B population.

    ## Example
    Container `my_space:AssetContainer` requires `my_space:DescribableContainer`. The
    `DescribableContainer` has a non-nullable property `name`. If no view maps to both
    `AssetContainer` and `DescribableContainer.name`, then `DescribableContainer` must be
    populated separately before any view using `AssetContainer` can be used for ingestion.
    """

    code = f"{BASE_CODE}-007"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        merged_views = self.validation_resources.merged.views
        merged_containers = self.validation_resources.merged.containers
        local_containers = self.validation_resources.local.containers

        # Build mappings from view to (container, property) pairs
        view_to_container_properties: dict[str, set[tuple[ContainerReference, str]]] = {}
        for view_ref, view in merged_views.items():
            if not view.properties:
                continue
            container_props: set[tuple[ContainerReference, str]] = set()
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    container_props.add((property_.container, property_.container_property_identifier))
            if container_props:
                view_to_container_properties[str(view_ref)] = container_props

        # Check each local container's requires constraints
        for container_a_ref, container_a in local_containers.items():
            if not container_a.constraints:
                continue

            for constraint in container_a.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                container_b_ref = constraint.require
                container_b = merged_containers.get(container_b_ref)

                if container_b is None:
                    continue  # Handled by RequiredContainerDoesNotExist

                if not self.validation_resources.containers_appear_together(container_a_ref, container_b_ref):
                    continue  # Handled by UnnecessaryRequiresConstraint

                # Get all non-nullable properties of container B
                non_nullable_props: set[str] = set()
                for prop_id, prop_def in container_b.properties.items():
                    if prop_def.nullable is False:
                        non_nullable_props.add(prop_id)

                if not non_nullable_props:
                    # No non-nullable properties in B - no issue
                    continue

                # Check if any view covers both A and all non-nullable properties of B
                covers_all = False
                for container_props in view_to_container_properties.values():
                    # Check if this view maps to container A
                    maps_to_a = any(c_ref == container_a_ref for c_ref, _ in container_props)
                    if not maps_to_a:
                        continue

                    # Check if this view maps to all non-nullable properties of B
                    b_props_in_view = {prop_id for c_ref, prop_id in container_props if c_ref == container_b_ref}
                    if non_nullable_props <= b_props_in_view:
                        covers_all = True
                        break

                if not covers_all:
                    missing_props_str = ", ".join(sorted(non_nullable_props))
                    recommendations.append(
                        Recommendation(
                            message=(
                                f"Container '{container_a_ref!s}' requires '{container_b_ref!s}', but no view maps "
                                f"to both '{container_a_ref!s}' and all non-nullable properties of '{container_b_ref!s}' "
                                f"(non-nullable properties: {missing_props_str}). This means '{container_b_ref!s}' must "
                                f"be populated separately before views using '{container_a_ref!s}' can be used for ingestion."
                            ),
                            fix="Create a view that maps to both containers including all non-nullable properties, or make the required container's properties nullable",
                            code=self.code,
                        )
                    )

        return recommendations
