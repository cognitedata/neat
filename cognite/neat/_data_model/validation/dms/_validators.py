from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import DirectNodeRelation
from cognite.neat._data_model.models.dms._references import ContainerDirectReference, ContainerReference, DataModelReference, ViewDirectReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, IssueList, Recommendation


class ViewsWithoutProperties(DataModelValidator):
    """This validator checks for views without properties, i.e. views that do not have any
    property attached to them , either directly or through implements."""

    code = "NEAT-DMS-001"

    def __init__(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

    def run(self) -> list[ConsistencyError]:
        views_without_properties = []

        for ref, view in self.local_views_by_reference.items():
            if not view.properties:
                # Existing CDF view has properties
                if (
                    self.cdf_views_by_reference
                    and (remote := self.cdf_views_by_reference.get(ref))
                    and remote.properties
                ):
                    continue

                # Implemented views have properties
                if view.implements and any(
                    self.cdf_views_by_reference
                    and (remote_implement := self.cdf_views_by_reference.get(implement))
                    and remote_implement.properties
                    for implement in view.implements or []
                ):
                    continue

                views_without_properties.append(ref)

        return [
            ConsistencyError(
                message=(
                    f"View {ref!s} does "
                    "not have any properties defined, either directly or through implements."
                    " This will prohibit your from deploying the data model to CDF."
                ),
                fix="Define properties for the view",
                code=self.code,
            )
            for ref in views_without_properties
        ]


class UndefinedConnectionEndNodeTypes(DataModelValidator):
    """This validator checks for connections where the end node types are not defined"""

    code = "NEAT-DMS-002"

    def __init__(
        self,
        local_connection_end_node_types: dict[tuple[ViewReference, str], ViewReference],
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_connection_end_node_types = local_connection_end_node_types
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

    def run(self) -> list[ConsistencyError]:
        undefined_value_types = []

        for (view, property_), value_type in self.local_connection_end_node_types.items():
            if value_type not in self.local_views_by_reference and value_type not in self.cdf_views_by_reference:
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

    def __init__(
        self,
        data_model_reference: DataModelReference,
        view_references: list[ViewReference],
    ) -> None:
        self.data_model_reference = data_model_reference
        self.view_references = view_references

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.view_references:
            issue_description = ""

            if view_ref.space not in COGNITE_SPACES:
                # notify about inconsisten space
                if view_ref.space != self.data_model_reference.space:
                    issue_description = f"space (view: {view_ref.space}, data model: {self.data_model_reference.space})"

                # or version if spaces are same
                elif view_ref.version != self.data_model_reference.version:
                    issue_description = (
                        f"version (view: {view_ref.version}, data model: {self.data_model_reference.version})"
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

class BidirectionalConnectionMisconfigured(DataModelValidator):
    """This validator checks for bidirectional connections, reverse - direct pairs, where the direct part of the connection
    is not configured in a way that it points back to the reverse connection's view.

    Some examples of misconfigurations are:
    - A reverse connection points to a view through a property (direct connection) which in turn points to another view (results in Consistency Error)
    - A direct part of a bidirectional value type is not configured as a direct relation property (results in Consistency Error)
    - A direct part of a bidirectional value type is None (results in Recommendation)

    The latter misconfiguration occurs is a hack used by users to create a multi value direct relations. This allows users to
    create multiple reverse direct relations through this property. In CDF Search this will give you a multi value direct relation.
    """

    code = "NEAT-DMS-004"

    def __init__(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
        reverse_to_direct_mapping: dict[tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]],
        local_containers_by_reference: dict[ContainerReference, ContainerRequest],
        cdf_containers_by_reference: dict[ContainerReference, ContainerRequest],
    ) -> None:

        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference
        self.reverse_to_direct_mapping = reverse_to_direct_mapping
        self.local_containers_by_reference = local_containers_by_reference
        self.cdf_containers_by_reference = cdf_containers_by_reference

    def _select_source_view(self, view_ref: ViewReference, through: ViewDirectReference) -> ViewRequest | None:
        local_view = self.local_views_by_reference.get(view_ref)
        cdf_view = self.cdf_views_by_reference.get(view_ref)

        # set correct view, since we condier partal dat amodel
        source_view = None
        if local_view and local_view.properties and through.identifier in local_view.properties:
            source_view = local_view
        elif cdf_view and cdf_view.properties and through.identifier in cdf_view.properties:
            source_view = cdf_view

        return source_view

    def _select_source_container(self, container_ref: ContainerReference, container_property: str) -> ContainerRequest | None:
        local_container = self.local_containers_by_reference.get(container_ref)
        cdf_container = self.cdf_containers_by_reference.get(container_ref)

        # set correct container, since we condier partal data model
        source_container = None
        if local_container and local_container.properties and container_property in local_container.properties:
            source_container = local_container
        elif cdf_container and cdf_container.properties and container_property in cdf_container.properties:
            source_container = cdf_container

        return source_container

    def run(self) -> list[ConsistencyError] | list[Recommendation]:
        issues: IssueList = []

        for (target_view_ref, reverse_prop_name), (source_view_ref, through) in self.reverse_to_direct_mapping.items():
            if isinstance(through, ViewDirectReference):

                # need to select correct source view
                # and correct source container
                source_view = self._select_source_view(source_view_ref, through)

                # this should be caught by UndefinedConnectionEndNodeTypes as well
                if not source_view:
                    issues.append(ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} is not defined in the data model nor exists in CDF."
                        ),
                        fix="Define necessary view",
                        code=self.code,
                    ))
                    continue

                # this should be caught by ViewsWithoutProperties as well
                if not source_view.properties:
                    issues.append(ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} does not have any properties defined."
                        ),
                        fix="Define necessary view properties",
                        code=self.code,
                    ))
                    continue


                direct_prop_name = through.identifier
                source_property = source_view.properties.get(direct_prop_name)

                # source property does not exist
                if not source_property:
                    issues.append(ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} does not have property "
                            f"{direct_prop_name!s} defined which is used to point back to the target view."
                        ),
                        fix="Define necessary view property",
                        code=self.code,
                    ))
                    continue

                # source property exists, but it is not a direct relation property
                if not isinstance(source_property, ViewCorePropertyRequest):
                    issues.append(ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} has property "
                            f"{direct_prop_name!s} defined which is not a direct relation property."
                        ),
                        fix="Change view property to be a direct relation property",
                        code=self.code,
                    ))
                    continue

                
                # Here we start checking if the direct property actually exists in the container
                # and if it is of the correct type
                container_ref, container_property_identifier = source_property.container, source_property.container_property_identifier

                source_container = self._select_source_container(container_ref, container_property_identifier)


                if not source_container:
                    issues.append(ConsistencyError(
                        message=(
                            f"Container {container_ref!s} for source view {source_view_ref!s} property "
                            f"{direct_prop_name!s} used in reverse connection {reverse_prop_name!s} in target view {target_view_ref!s} "
                            "is not defined in the data model nor exists in CDF."
                        ),
                        fix="Define necessary container",
                        code=self.code,
                    ))
                    continue

                container_property = source_container.properties.get(container_property_identifier)

                if not container_property:
                    issues.append(ConsistencyError(
                        message=(
                            f"Container {container_ref!s} for source view {source_view_ref!s} property "
                            f"{direct_prop_name!s} used in reverse connection {reverse_prop_name!s} in target view {target_view_ref!s} "
                            f"does not have property {container_property_identifier!s} defined."
                        ),
                        fix="Define necessary container property",
                        code=self.code,
                    ))
                    continue

                container_property_type = container_property.type

                if not isinstance(container_property_type, DirectNodeRelation):
                    issues.append(ConsistencyError(
                        message=(
                            f"Container {container_ref!s} for source view {source_view_ref!s} property "
                            f"{direct_prop_name!s} used in reverse connection {reverse_prop_name!s} in target view {target_view_ref!s} "
                            f"has property {container_property_identifier!s} of type {container_property_type!s} which is not a direct node relation."
                        ),
                        fix="Change container property type to be a direct node relation",
                        code=self.code,
                    ))
                    continue

                actual_target_view = source_property.source

                # Typical hack used to make SEARCH to work
                if not actual_target_view:
                    issues.append(Recommendation(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} has property "
                            f"{direct_prop_name!s} which value type is expected to be {target_view_ref!s} "
                            "but it is not explicitly defined."
                        ),
                        fix="Define necessary value type for the source view property",
                        code=self.code,
                    ))
                    continue
                
                if actual_target_view != target_view_ref:
                    issues.append(ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} for reverse connection "
                            f"{reverse_prop_name!s} in target view {target_view_ref!s} has property "
                            f"{direct_prop_name!s} which points to view {actual_target_view!s} "
                            "but it is expected to point back to the target view."
                        ),
                        fix="Reconfigure direct connection to point back to the target view",
                        code=self.code,
                    ))

        return issues
