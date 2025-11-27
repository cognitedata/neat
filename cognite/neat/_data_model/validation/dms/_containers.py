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
