"""Validators for checking containers in the data model."""

from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError

BASE_CODE = "NEAT-DMS-VIEW"


class ViewToContainerMappingNotPossible(DataModelValidator):
    """Validates that container and container property referenced by view property exist.

    ## What it does
    Validates that for each view property that maps to a container and container property,
    the referenced container and container property exist.

    ## Why is this bad?
    If a view property references a container or container property that does not exist,
    the data model cannot be deployed to CDF. This means that view property will not be able to function.

    ## Example
    View WindTurbine has property location that maps to container WindTurbineContainer and property gpsCoordinates.
    If WindTurbineContainer and/or property gpsCoordinates does not exist, the data model cannot be deployed to CDF.
    """

    code = f"{BASE_CODE}-001"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for view_ref, view in self.local_resources.views_by_reference.items():
            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                container_ref = property_.container
                container_property = property_.container_property_identifier

                container = self._select_container_with_property(container_ref, container_property)

                if not container:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} maps to "
                                f"container {container_ref!s} which does not exist."
                            ),
                            fix="Define necessary container",
                            code=self.code,
                        )
                    )
                elif container_property not in container.properties:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} maps to "
                                f"container {container_ref!s} which does not have "
                                f"property '{container_property}'."
                            ),
                            fix="Define necessary container property",
                            code=self.code,
                        )
                    )

        return errors
