"""Validators for checking containers in the data model."""

from cognite.neat._data_model._fix import FixAction
from cognite.neat._data_model.deployer.data_classes import RemovedField, SeverityType
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._issues import ConsistencyError

BASE_CODE = "NEAT-DMS-CONTAINER"


class ExternalContainerDoesNotExist(DataModelRule):
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

    def validate(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if not self.validation_resources.merged_data_model.views:
            return errors

        for view_ref in self.validation_resources.merged_data_model.views:
            view = self.validation_resources.select_view(view_ref)

            # it will be captured by another validator
            if view is None:
                continue

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


class ExternalContainerPropertyDoesNotExist(DataModelRule):
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

    def validate(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if self.validation_resources.merged_data_model.views:
            for view_ref in self.validation_resources.merged_data_model.views:
                view = self.validation_resources.select_view(view_ref)

                # it will be captured by another validator
                if view is None:
                    continue

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


class RequiredContainerDoesNotExist(DataModelRule):
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

    def validate(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for container_ref in self.validation_resources.merged.containers:
            container = self.validation_resources.select_container(container_ref)

            if not container:
                raise RuntimeError(
                    f"{type(self).__name__}: Container {container_ref!s} "
                    "not found in local resources. This is a bug in NEAT."
                )

            for constraint_ref, constraint in self.validation_resources.get_requires_constraints(container):
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


class RequiresConstraintCycle(DataModelRule):
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

    code = f"{BASE_CODE}-005"
    issue_type = ConsistencyError
    alpha = True  # Still in development
    fixable = True

    def validate(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []
        for cycle in self.validation_resources.requires_constraint_cycles:
            cycle_str = " -> ".join(str(c) for c in cycle) + f" -> {cycle[0]!s}"
            source_container_ref, required_container_ref = self.validation_resources.pick_cycle_constraint_to_remove(
                cycle
            )
            errors.append(
                ConsistencyError(
                    message=(
                        f"Requires constraints form a cycle: {cycle_str}. This can be fixed by removing the requires "
                        f"constraint on {source_container_ref!s} to {required_container_ref!s}"
                    ),
                    fix="Remove the recommended requires constraint to break the cycle",
                    code=self.code,
                )
            )

        return errors

    def fix(self) -> list[FixAction]:
        """Return fix actions to break requires constraint cycles."""
        fix_actions: list[FixAction] = []
        # Overlapping cycles can share the same edge to remove. Dedup here
        # because each constraint only needs to be removed once.
        seen: set[tuple[ContainerReference, ContainerReference]] = set()

        for cycle in self.validation_resources.requires_constraint_cycles:
            source_container_ref, required_container_ref = self.validation_resources.pick_cycle_constraint_to_remove(
                cycle
            )
            if (source_container_ref, required_container_ref) in seen:
                continue
            seen.add((source_container_ref, required_container_ref))

            container = self.validation_resources.select_container(source_container_ref)
            if not container:
                continue
            for constraint_id, constraint_def in self.validation_resources.get_requires_constraints(container):
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
                        message="Removed requires constraint to break cycle",
                    )
                )

        return fix_actions
