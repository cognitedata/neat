"""Validators for checking containers in the data model."""

from pyparsing import cast

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

            for external_id, constraint in cast(dict[str, Constraint], container.constraints).items():
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

        # Build container -> views mapping (which views use each container)
        container_to_views: dict[ContainerReference, set[str]] = {}

        for view_ref, view in self.merged_views.items():
            if not view.properties:
                continue
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    container_ref = property_.container
                    if container_ref not in container_to_views:
                        container_to_views[container_ref] = set()
                    container_to_views[container_ref].add(str(view_ref))

        # Build view -> containers mapping
        view_to_containers: dict[str, set[ContainerReference]] = {}
        for view_ref, view in self.merged_views.items():
            if not view.properties:
                continue
            containers: set[ContainerReference] = set()
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    containers.add(property_.container)
            if containers:
                view_to_containers[str(view_ref)] = containers

        def get_direct_required_containers(container_ref: ContainerReference) -> set[ContainerReference]:
            """Get all containers that a container directly requires."""
            container = self.merged_containers.get(container_ref)
            if not container or not container.constraints:
                return set()

            required: set[ContainerReference] = set()
            for constraint in cast(dict[str, Constraint], container.constraints).values():
                if isinstance(constraint, RequiresConstraintDefinition):
                    required.add(constraint.require)
            return required

        def get_transitively_required(
            container_ref: ContainerReference, visited: set[ContainerReference] | None = None
        ) -> set[ContainerReference]:
            """Get all containers that a container requires (transitively)."""
            if visited is None:
                visited = set()
            if container_ref in visited:
                return set()
            visited.add(container_ref)

            direct_required = get_direct_required_containers(container_ref)
            all_required = direct_required.copy()
            for req in direct_required:
                all_required.update(get_transitively_required(req, visited))
            return all_required

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
            transitively_required = get_transitively_required(container_a)

            # Collect all containers that A should require but doesn't yet
            missing_requirements: set[ContainerReference] = set()

            for container_b in containers_with_a:
                # Skip if A already transitively requires B
                if container_b in transitively_required:
                    continue

                views_with_b = container_to_views.get(container_b, set())

                # Check if A ever appears without B
                # If views_with_a is a subset of views_with_b, then A never appears without B
                a_always_with_b = views_with_a <= views_with_b

                if a_always_with_b:
                    missing_requirements.add(container_b)

            # Find the minimal set of constraints needed
            # Remove any container B if another container C in the set transitively requires B
            # (because adding A -> C would transitively cover B)
            minimal_requirements: set[ContainerReference] = set()
            for container_b in missing_requirements:
                # Check if B is transitively required by any other container in missing_requirements
                covered_by_other = False
                for container_c in missing_requirements:
                    if container_c != container_b and container_b in get_transitively_required(container_c):
                        covered_by_other = True
                        break
                if not covered_by_other:
                    minimal_requirements.add(container_b)

            for container_b in minimal_requirements:
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

        return recommendations
