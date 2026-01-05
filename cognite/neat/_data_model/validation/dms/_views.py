"""Validators for checking views in the data model."""

from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

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
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if not self.validation_resources.merged_data_model.views:
            return errors

        for view_ref in self.validation_resources.merged_data_model.views:
            view = self.validation_resources.select_view(view_ref)

            if not view:
                raise RuntimeError(
                    f"ViewToContainerMappingNotPossible.run: View {view_ref!s} "
                    "not found in local resources. This is a bug in NEAT."
                )

            if view.properties is None:
                continue

            for property_ref, property_ in view.properties.items():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                container_ref = property_.container
                container_property = property_.container_property_identifier

                container = self.validation_resources.select_container(container_ref, container_property)

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


class ImplementedViewNotExisting(DataModelValidator):
    """Validates that implemented (inherited) view exists.

    ## What it does
    Validates that all views which are implemented (inherited) in the data model actually exist either locally
    or in CDF.

    ## Why is this bad?
    If a view being implemented (inherited) does not exist, the data model cannot be deployed to CDF.

    ## Example
    If view WindTurbine implements (inherits) view Asset, but Asset view does not exist in the data model
    or in CDF, the data model cannot be deployed to CDF.
    """

    code = f"{BASE_CODE}-002"
    issue_type = ConsistencyError

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        if not self.validation_resources.merged_data_model.views:
            return errors

        for view_ref in self.validation_resources.merged_data_model.views:
            view = self.validation_resources.select_view(view_ref)

            if not view:
                raise RuntimeError(
                    f"ImplementedViewNotExisting.run: View {view_ref!s} "
                    "not found in local resources. This is a bug in NEAT."
                )

            if view.implements is None:
                continue
            for implement in view.implements:
                if self.validation_resources.select_view(implement) is None:
                    errors.append(
                        ConsistencyError(
                            message=f"View {view_ref!s} implements {implement!s} which is not defined.",
                            fix="Define the missing view or remove it from the implemented views list",
                            code=self.code,
                        )
                    )

        return errors


class MappedContainersMissingRequiresConstraint(DataModelValidator):
    """
    Validates that views mapping to multiple containers have a requires hierarchy between them.

    ## What it does
    For each view that maps to two or more containers, this validator checks whether there is
    a complete hierarchy of requires constraints between all mapped containers. Specifically,
    for any pair of mapped containers A and B, at least one must require the other (directly
    or transitively).

    ## Why is this bad?
    When querying a view without filters, the API uses `hasData` filters on all mapped containers.
    If there's no requires hierarchy, each container needs a separate `hasData` check, which
    triggers expensive joins. With a proper requires hierarchy, the `hasData` check can be
    optimized to only check the "root" container.

    ## Example
    View `Pump` maps to containers `Pump` and `CogniteDescribable`.
    If neither container requires the other, queries will perform two separate `hasData` checks
    with a join. Adding `Pump requires CogniteDescribable` allows the query
    optimizer to reduce this to a single `hasData` check.
    """

    code = f"{BASE_CODE}-003"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        view_to_containers = self.validation_resources.view_to_containers
        local_views = self.validation_resources.local.views

        for view_ref in local_views:
            view_ref_str = str(view_ref)
            containers_in_view = view_to_containers.get(view_ref_str, set())

            if len(containers_in_view) < 2:
                continue  # Single container or no containers - no hierarchy needed

            # Check if there's a container that requires all others (directly or indirectly)
            if self.validation_resources.has_root_container(containers_in_view):
                continue  # Performance optimization is possible

            # Find containers that aren't required by any other - these need to be connected
            uncovered = self.validation_resources.find_uncovered_containers(containers_in_view)
            if len(uncovered) > 1:
                uncovered_str = ", ".join(f"'{c!s}'" for c in sorted(uncovered, key=str))
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' maps to {len(containers_in_view)} containers but no single "
                            f"container requires all the others. The following containers are missing a requires "
                            f"constraint with another container: {uncovered_str}. "
                            f"This can cause suboptimal performance when querying instances through this view."
                        ),
                        fix=(
                            "Add requires constraints between the containers, such that one container "
                            "requires all the others, either directly or indirectly"
                        ),
                        code=self.code,
                    )
                )

        return recommendations


class MappedContainerRequiresUnmappedContainer(DataModelValidator):
    """
    Validates that views don't map to containers that require unmapped containers.

    ## What it does
    For each view, this validator checks whether any mapped container requires a container
    that is NOT mapped in the same view. This includes both direct and transitive requires
    constraints.

    ## Why is this bad?
    If a view maps to container A which requires container B, but B is not mapped in the view,
    then ingestion through this view is complicated:
    - Container B must be populated separately before data can be ingested through this view
    - The view cannot be used for initial data population
    - Users must use the containers API or another view to populate container B first

    ## Example
    View `Equipment` maps only to `CogniteEquipment`, but `CogniteEquipment` requires
    `CogniteDescribable` (which has a non-nullable `name` property). Since `CogniteDescribable`
    is not mapped in the view, you cannot ingest data through `Equipment` until `CogniteDescribable`
    instances are created separately.
    """

    code = f"{BASE_CODE}-004"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        view_to_containers = self.validation_resources.view_to_containers
        local_views = self.validation_resources.local.views

        for view_ref in local_views:
            view_ref_str = str(view_ref)
            containers_in_view = view_to_containers.get(view_ref_str, set())

            if not containers_in_view:
                continue

            requiring_containers = self.validation_resources.find_unmapped_required_containers(containers_in_view)

            if requiring_containers:
                # Collect all unique unmapped containers
                all_unmapped: set[ContainerReference] = set()
                for unmapped in requiring_containers.values():
                    all_unmapped.update(unmapped)
                unmapped_str = ", ".join(f"'{c!s}'" for c in sorted(all_unmapped, key=str))

                recommendations.append(
                    Recommendation(
                        message=(
                            f"View '{view_ref!s}' maps to containers that require (directly or indirectly) "
                            f"the following unmapped containers: {unmapped_str}. Ingestion through this view "
                            f"requires the unmapped containers to be populated separately first."
                        ),
                        fix=(
                            "Consider adding mappings for the required containers to this view, "
                            "or remove the requires constraints if they're not needed"
                        ),
                        code=self.code,
                    )
                )

        return recommendations
