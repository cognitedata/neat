from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError

_BASE_CODE = "NEAT-DMS-CONTAINERS"


class ReferencedContainersExist(DataModelValidator):
    """This validator checks that all referenced containers in the data model exist either locally or in CDF."""

    code = f"{_BASE_CODE}-001"

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
                                f"View {view_ref!s} property {property_ref!s} references "
                                f"container {container_ref!s} which does not exist "
                                "in the data model nor in CDF."
                                " This will prohibit you from deploying the data model to CDF."
                            ),
                            fix="Define necessary container",
                            code=self.code,
                        )
                    )
                elif container_property not in container.properties:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} property {property_ref!s} references "
                                f"container {container_ref!s} which does not have "
                                f"property '{container_property}' defined."
                                " This will prohibit you from deploying the data model to CDF."
                            ),
                            fix="Define necessary container property",
                            code=self.code,
                        )
                    )

        return errors
