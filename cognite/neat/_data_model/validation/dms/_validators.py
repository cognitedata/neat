from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation


class UndefinedConnectionEndNodeTypes(DataModelValidator):
    """This validator checks for connections where the end node types are not defined"""

    code = "NEAT-DMS-002"

    def run(self) -> list[ConsistencyError]:
        undefined_value_types = []

        for (view, property_), value_type in self.local_resources.connection_end_node_types.items():
            if (
                value_type not in self.local_resources.views_by_reference
                and value_type not in self.cdf_resources.views_by_reference
            ):
                undefined_value_types.append((view, property_, value_type))

        return [
            ConsistencyError(
                message=(
                    f"View {view!s} property {property_!s} has value type {value_type!s} "
                    "which is not defined as a view in the data model neither exists in CDF."
                    " This will prohibit you from deploying the data model to CDF."
                ),
                fix="Define necessary view",
                code=self.code,
            )
            for (view, property_, value_type) in undefined_value_types
        ]


class VersionSpaceInconsistency(DataModelValidator):
    """This validator checks for inconsistencies in versioning and space among views and data model"""

    code = "NEAT-DMS-003"

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.local_resources.views_by_reference:
            issue_description = ""

            if view_ref.space not in COGNITE_SPACES:
                # notify about inconsisten space
                if view_ref.space != self.local_resources.data_model_reference.space:
                    issue_description = (
                        f"space (view: {view_ref.space}, data model: {self.local_resources.data_model_reference.space})"
                    )

                # or version if spaces are same
                elif view_ref.version != self.local_resources.data_model_reference.version:
                    issue_description = (
                        f"version (view: {view_ref.version}, "
                        f"data model: {self.local_resources.data_model_reference.version})"
                    )

            if issue_description:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View {view_ref!s} has inconsistent {issue_description} "
                            "with the data model."
                            " This may lead to more demanding development and maintenance efforts."
                        ),
                        fix="Update view version and/or space to match data model",
                        code=self.code,
                    )
                )

        return recommendations


class ReferencedContainersExist(DataModelValidator):
    """This validator checks that all referenced containers in the data model exist either locally or in CDF."""

    code = "NEAT-DMS-005"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for view_ref, view in self.local_resources.views_by_reference.items():
            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                container_ref = property_.container
                container_property = property_.container_property_identifier

                container = self._select_container(container_ref, container_property)

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
