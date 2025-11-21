"""Validators for checking containers in the data model."""

from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError

BASE_CODE = "NEAT-DMS-CONTAINER"


class ExternalContainerDoesNotExist(DataModelValidator):
    """
    Validates that any container or container property referenced by a view property, when the
    referenced container does not belong to the data model's space, exists in CDF.

    ## What it does
    For each view property that maps to a container in a different space than the data model,
    this validator checks that:
    - the referenced external container exists in CDF, and
    - that the referenced container property also exists in that external container.

    ## Why is this bad?
    If a view property references a container or container property that does not exist in CDF,
    the data model cannot be deployed. The affected view property will not function, and the
    deployment of the entire data model will fail.

    ## Example
    View `my_space:WindTurbine` has a property `location` that maps to container
    `other_space:WindTurbineContainer`, where `other_space` differs from `my_space`. If that
    container does not exist in CDF, the model cannot be deployed.

    Similarly, if a view property references `other_space:WindTurbineContainer` and its property
    `gpsCoordinates`, and `gpsCoordinates` does not exist in that container in CDF, deployment
    will also fail.
    """

    code = f"{BASE_CODE}-001"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for view_ref, view in self.merged_views.items():
            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                if property_.container.space == self.local_resources.data_model_reference.space:
                    continue

                # Check existence of container in CDF
                elif property_.container not in self.cdf_resources.containers_by_reference:
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

                # Check existence of container property in CDF
                elif (
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
