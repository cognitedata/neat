"""Validators for checking containers in the data model."""

from typing import cast

from cognite.neat._data_model.models.dms._constraints import Constraint, RequiresConstraintDefinition
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
                    f"{type(self).__name__}: View {view_ref!s} not found in local resources. This is a bug in NEAT."
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
                        f"{type(self).__name__}: View {view_ref!s} not found in local resources. This is a bug in NEAT."
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

        for container_ref in self.validation_resources.merged.containers:
            container = self.validation_resources.select_container(container_ref)

            if not container:
                raise RuntimeError(
                    f"{type(self).__name__}: Container {container_ref!s} "
                    "not found in local resources. This is a bug in NEAT."
                )

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


class UnnecessaryRequiresConstraint(DataModelValidator):
    """
    Validates that requires constraints between containers are meaningful.

    ## What it does
    For each container with a requires constraint, this validator checks whether the
    required container ever appears together with the requiring container in any view.
    If they never appear together, the requires constraint will not have any performance benefit.
    Requires constraints could still be useful for consistency checks however.

    ## Why is this bad?
    A requires constraint means that instances in the required container must be populated before
    they can be populated in the requiring container. If these containers never appear together in
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

        for container_ref in self.validation_resources.merged.containers:
            container = self.validation_resources.select_container(container_ref)

            if not container:
                raise RuntimeError(
                    f"{type(self).__name__}: Container {container_ref!s} not found in local resources. This is a bug in NEAT."
                )

            if not container.constraints:
                continue

            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue

                if constraint.require not in self.validation_resources.merged.containers:
                    continue  # Handled by RequiredContainerDoesNotExist

                if self.validation_resources.are_containers_mapped_together(container_ref, constraint.require):
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

        # Use pre-computed cycles from SCC (Tarjan's algorithm)
        for cycle_set in self.validation_resources.requires_constraint_cycles:
            # Format cycle for display
            cycle_list = list(cycle_set)
            cycle_str = " -> ".join(str(c) for c in cycle_list) + f" -> {cycle_list[0]!s}"
            errors.append(
                ConsistencyError(
                    message=f"Requires constraints form a cycle: {cycle_str}",
                    fix="Remove one of the requires constraints to break the cycle",
                    code=self.code,
                )
            )

        return errors
