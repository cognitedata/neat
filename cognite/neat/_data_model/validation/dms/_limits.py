from cognite.neat._data_model.models.dms._data_types import EnumProperty, ListablePropertyTypeDefinition
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._view_property import (
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.validation.dms._base import CDFResources, DataModelValidator, LocalResources
from cognite.neat._issues import ConsistencyError
from cognite.neat._utils.useful_types import ModusOperandi

_BASE_CODE = "NEAT-DMS-LIMITS"


class DataModelLimitValidator(DataModelValidator):
    """Validates that a DMS data model adheres to all CDF resource limits.

    This validator performs comprehensive limit checking across three levels:
    - Data Model Level
    - View Level
    - Container Level

    The validator supports two deployment modes:
    - **"rebuild" mode**: Validates only local data model resources
    - **"additive" mode**: Merges local + CDF resources for accurate limit checking

    All violations produce ConsistencyError issues that prevent deployment.
    """

    code = f"{_BASE_CODE}-001"

    def __init__(
        self,
        local_resources: LocalResources,
        cdf_resources: CDFResources,
        limits: SchemaLimits,
        modus_operandi: ModusOperandi = "additive",
    ) -> None:
        super().__init__(local_resources, cdf_resources, modus_operandi)
        self.limits = limits

    def run(self) -> list[ConsistencyError]:
        """Execute all limit validations on the data model.

        Performs three levels of validation:
        1. Data model limits (view count)
        2. View limits (properties, containers, implements)
        3. Container limits (properties, list sizes)

        Returns:
            List of ConsistencyError issues for any limit violations found.
            Empty list if all limits are satisfied.
        """
        errors: list[ConsistencyError] = []

        errors.extend(self._data_model_limit_check())
        errors.extend(self._views_limit_check())
        errors.extend(self._containers_limit_check())

        return errors

    def _data_model_limit_check(self) -> list[ConsistencyError]:
        """Validate that the data model does not exceed the maximum number of views.

        Checks that total view count (local + CDF in additive mode) does not exceed the limit.

        Returns:
            List with single ConsistencyError if limit exceeded, empty list otherwise.
        """

        if len(self.data_model_view_references) > self.limits.data_models.views:
            return [
                ConsistencyError(
                    message=(
                        f"The data model references {len(self.data_model_view_references)} views, "
                        "which exceeds the limit of "
                        f"{self.limits.data_models.views} views per data model."
                    ),
                    code=self.code,
                )
            ]
        return []

    def _views_limit_check(self) -> list[ConsistencyError]:
        """Validate that no view exceeds properties, containers, or implements limits.

        For each view in the data model, checks:
        - Properties count
        - Unique container references
        - Implemented views count

        In additive mode, counts include properties and implements from both local
        and CDF versions of the view.

        Returns:
            List of ConsistencyError issues, one per limit violation found.
            Empty list if all views are within limits.
        """

        errors: list[ConsistencyError] = []

        merged_views = self.merged_views

        for view_ref in self.local_resources.views_by_reference.keys():
            view = merged_views.get(view_ref)
            if not view:
                raise RuntimeError(f"View {view_ref!s} not found in merged views. This is a bug!")

            if view.properties:
                if len(view.properties) > self.limits.views.properties:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} has {len(view.properties)} properties, which exceeds the limit of "
                                f"{self.limits.views.properties} properties per view."
                            ),
                            code=self.code,
                        )
                    )

                if (
                    count := len(
                        {
                            prop.container
                            for prop in view.properties.values()
                            if (isinstance(prop, ViewCorePropertyRequest) and prop.container)
                        }
                    )
                ) and count > self.limits.views.containers:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} references "
                                f"{count} containers, which exceeds the limit of "
                                f"{self.limits.views.containers} containers per view."
                            ),
                            code=self.code,
                        )
                    )
            else:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"View {view_ref!s} does "
                            "not have any properties defined, either directly or through implements."
                            " This will prohibit your from deploying the data model to CDF."
                        ),
                        fix="Define at least one property for view",
                        code=self.code,
                    )
                )

            if view.implements:
                if len(view.implements) > self.limits.views.implements:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} implements {len(view.implements)} views, which exceeds the limit of"
                                f" {self.limits.views.implements} implemented views per view."
                            ),
                            code=self.code,
                        )
                    )

        return errors

    def _containers_limit_check(self) -> list[ConsistencyError]:
        """Validate that no container exceeds properties or list size limits.

        For each container in the data model, checks:
        - List size (max_list_size) ≤ appropriate limit based on:
          * Data type (Int32, Int64, DirectRelation, etc.)
          * Presence of btree index
          * Default vs maximum limits

        Enum properties are skipped (have separate 32-value limit), which is checked on read time as SyntaxError check.

        In additive mode, counts include properties from both local and CDF
        versions of the container.

        Returns:
            List of ConsistencyError issues, one per limit violation found.
            Empty list if all containers are within limits.
        """

        errors: list[ConsistencyError] = []

        merged_containers = self.merged_containers

        for container_ref in self.local_resources.containers_by_reference.keys():
            container = merged_containers.get(container_ref)
            if not container:
                raise RuntimeError(f"Container {container_ref!s} not found in merged containers. This is a bug!")

            if not container.properties:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} does not have any properties defined."
                            " This will prohibit your from deploying the data model to CDF."
                        ),
                        fix="Define at least one property for container",
                        code=self.code,
                    )
                )

            properties_by_index_type = self.container_property_by_index_type(container)

            if len(container.properties) > self.limits.containers.properties():
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} has {len(container.properties)} properties, "
                            "which exceeds the limit of "
                            f"{self.limits.containers.properties()} properties per container."
                        ),
                        code=self.code,
                    )
                )

            for property_id, property_ in container.properties.items():
                type_ = property_.type

                if isinstance(type_, EnumProperty):
                    continue

                if not isinstance(type_, ListablePropertyTypeDefinition) or type_.max_list_size is None:
                    continue

                has_btree_index = property_id in properties_by_index_type[BtreeIndex.model_fields["index_type"].default]
                limit = self.limits.containers.properties.listable(type_, has_btree_index)
                if type_.max_list_size > limit:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"Container {container_ref!s} has property {property_id} with list size "
                                f"{type_.max_list_size}, which exceeds the limit of {limit} "
                                f"for data type {type_.__class__.__name__}."
                            ),
                            code=self.code,
                        )
                    )

        return errors
