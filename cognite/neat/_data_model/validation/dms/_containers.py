"""Validators for checking containers in the data model."""

from pyparsing import cast

from cognite.neat._data_model.models.dms._constraints import Constraint, RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError

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
