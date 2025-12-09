"""Validators for checking containers in the data model."""

from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

BASE_CODE = "NEAT-DMS-CONTAINER"


def _build_container_to_views_mapping(
    views_by_reference: dict[ViewReference, ViewRequest],
) -> dict[ContainerReference, set[str]]:
    """Build a mapping from container references to the views that use them."""
    container_to_views: dict[ContainerReference, set[str]] = {}
    for view_ref, view in views_by_reference.items():
        if not view.properties:
            continue
        for property_ in view.properties.values():
            if isinstance(property_, ViewCorePropertyRequest):
                container_ref = property_.container
                if container_ref not in container_to_views:
                    container_to_views[container_ref] = set()
                container_to_views[container_ref].add(str(view_ref))
    return container_to_views


def _get_direct_required_containers(
    container_ref: ContainerReference,
    containers_by_reference: dict[ContainerReference, ContainerRequest],
) -> set[ContainerReference]:
    """Get all containers that a container directly requires."""
    container = containers_by_reference.get(container_ref)
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
    visited: set[ContainerReference] | None = None,
) -> set[ContainerReference]:
    """Get all containers that a container requires (transitively)."""
    if visited is None:
        visited = set()
    if container_ref in visited:
        return set()
    visited.add(container_ref)

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
    visited: set[ContainerReference] | None = None,
    path: list[ContainerReference] | None = None,
) -> list[ContainerReference] | None:
    """Find a cycle in requires constraints starting from 'start' through 'current'.

    Returns the cycle path if found, None otherwise.
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []

    if current in visited:
        if current == start:
            return path + [current]
        return None

    visited.add(current)
    path.append(current)

    for required in _get_direct_required_containers(current, containers_by_reference):
        cycle = _find_requires_constraint_cycle(start, required, containers_by_reference, visited, path)
        if cycle:
            return cycle

    path.pop()
    return None


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

        for view_ref, view in self.merged_views.items():
            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                if property_.container.space == self.local_resources.data_model_reference.space:
                    continue

                # Check existence of container in CDF
                if property_.container not in self.cdf_resources.containers_by_reference:
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

        for view_ref, view in self.merged_views.items():
            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                if property_.container.space == self.local_resources.data_model_reference.space:
                    continue

                # Only check property if container exists in CDF
                # this check is done in ExternalContainerDoesNotExist
                if property_.container not in self.cdf_resources.containers_by_reference:
                    continue

                # Check existence of container property in CDF
                if (
                    property_.container_property_identifier
                    not in self.cdf_resources.containers_by_reference[property_.container].properties
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

        for container_ref, container in self.local_resources.containers_by_reference.items():
            if not container.constraints:
                continue

            for external_id, constraint in container.constraints.items():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                is_local = constraint.require.space == self.local_resources.data_model_reference.space
                container_exists = (
                    constraint.require in self.merged_containers
                    if is_local
                    else constraint.require in self.cdf_resources.containers_by_reference
                )

                if not container_exists:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"Container '{container_ref!s}' constraint '{external_id}' requires container "
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

        container_to_views = _build_container_to_views_mapping(self.merged_views)
        view_to_containers = _build_view_to_containers_mapping(self.merged_views)

        # For each local container, check if it should require other containers
        for container_a, views_with_a in container_to_views.items():
            # Only check local containers
            if container_a.space != self.local_resources.data_model_reference.space:
                continue
            if container_a not in self.local_resources.containers_by_reference:
                continue

            # Find all containers that appear with A in any view
            containers_with_a: set[ContainerReference] = set()
            for view_str in views_with_a:
                containers_with_a.update(view_to_containers.get(view_str, set()))
            containers_with_a.discard(container_a)

            # Get what A already transitively requires
            transitively_required = _get_transitively_required_containers(container_a, self.merged_containers)

            # Collect containers that A should require:
            # - always_required: A always appears with B (strongest case)
            # - optional_required: A appears with B in multi-container views, but alone in single-container views
            always_required: set[ContainerReference] = set()
            optional_required: set[ContainerReference] = set()

            for container_b in containers_with_a:
                # Skip if A already transitively requires B
                if container_b in transitively_required:
                    continue

                views_with_b = container_to_views.get(container_b, set())

                # Check if A ever appears without B
                # If views_with_a is a subset of views_with_b, then A never appears without B
                a_always_with_b = views_with_a <= views_with_b

                if a_always_with_b:
                    always_required.add(container_b)
                else:
                    # Check if A only appears without B in single-container views
                    views_without_b = views_with_a - views_with_b
                    all_single_container = all(
                        len(view_to_containers.get(view_str, set())) == 1 for view_str in views_without_b
                    )
                    if all_single_container and views_without_b:
                        optional_required.add(container_b)

            # Find containers that could provide better coverage:
            # containers that A appears with (but not always), that transitively cover items in always_required
            better_coverage: set[ContainerReference] = set()
            for container_c in containers_with_a:
                if container_c in transitively_required:
                    continue
                if container_c in always_required:
                    continue
                # Check if C transitively covers any container in always_required
                c_covers = _get_transitively_required_containers(container_c, self.merged_containers)
                if c_covers & always_required:
                    better_coverage.add(container_c)

            # Find the minimal set of constraints needed for always_required
            # Remove any container B if another container C in always_required transitively requires B
            minimal_always: set[ContainerReference] = set()
            for container_b in always_required:
                # Check if B is transitively covered by another container in always_required
                covered_by_other_in_set = any(
                    container_b in _get_transitively_required_containers(container_c, self.merged_containers)
                    for container_c in always_required
                    if container_c != container_b
                )
                if not covered_by_other_in_set:
                    minimal_always.add(container_b)

            # Find the minimal set for optional_required (also considering always_required)
            minimal_optional: set[ContainerReference] = set()
            for container_b in optional_required:
                # Skip if already covered by always_required
                if container_b in always_required:
                    continue
                covered_by_always = any(
                    container_b in _get_transitively_required_containers(container_c, self.merged_containers)
                    for container_c in always_required
                )
                if covered_by_always:
                    continue
                covered_by_other = any(
                    container_b in _get_transitively_required_containers(container_c, self.merged_containers)
                    for container_c in optional_required
                    if container_c != container_b
                )
                if not covered_by_other:
                    minimal_optional.add(container_b)

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

            # Recommend better coverage containers (containers that would transitively cover always_required)
            for container_c in better_coverage:
                views_with_c = container_to_views.get(container_c, set())
                views_without_c = views_with_a - views_with_c
                c_covers = _get_transitively_required_containers(container_c, self.merged_containers) & always_required
                covered_str = ", ".join(f"'{c!s}'" for c in c_covers)
                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' appears with container '{container_c!s}' in some views. "
                            f"Adding a requires constraint on '{container_c!s}' would transitively cover {covered_str} "
                            f"and provide better query performance. However, this would complicate ingestion for views "
                            f"where '{container_a!s}' appears without '{container_c!s}'."
                        ),
                        fix="Consider adding a requires constraint for better query performance in shared views",
                        code=self.code,
                    )
                )

            for container_b in minimal_optional:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"Container '{container_a!s}' is used together with container '{container_b!s}' "
                            f"in multi-container views, but also appears alone in single-container views. "
                            f"Adding a requires constraint would improve query performance for the multi-container views, "
                            f"but may complicate ingestion through the single-container views."
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

        container_to_views = _build_container_to_views_mapping(self.merged_views)

        # Check each local container's requires constraints
        for container_ref, container in self.local_resources.containers_by_reference.items():
            if not container.constraints:
                continue

            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                required_container = constraint.require

                # Get views that use each container
                views_with_requiring = container_to_views.get(container_ref, set())
                views_with_required = container_to_views.get(required_container, set())

                # Check if they ever appear together in any view
                views_in_common = views_with_requiring & views_with_required

                if not views_in_common:
                    recommendations.append(
                        Recommendation(
                            message=(
                                f"Container '{container_ref!s}' has a requires constraint on "
                                f"'{required_container!s}', but they never appear together in any view. "
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
        for container_ref in self.local_resources.containers_by_reference:
            cycle = _find_requires_constraint_cycle(container_ref, container_ref, self.merged_containers)
            if cycle:
                # Create a frozenset of the cycle to avoid reporting the same cycle multiple times
                cycle_set = frozenset(cycle[:-1])  # Exclude the duplicate end element
                if cycle_set not in reported_cycles:
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
