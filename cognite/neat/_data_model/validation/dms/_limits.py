"""Validators for checking if defined data model is within CDF DMS schema limits."""

from typing import Literal

from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import EnumProperty, ListablePropertyTypeDefinition
from cognite.neat._data_model.models.dms._indexes import BtreeIndex, InvertedIndex
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._view_property import (
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.validation.dms._base import (
    CDFResources,
    DataModelValidator,
    LocalResources,
)
from cognite.neat._issues import ConsistencyError
from cognite.neat._utils.useful_types import ModusOperandi

BASE_CODE = "NEAT-DMS-LIMITS"


class DataModelViewCountIsOutOfLimits(DataModelValidator):
    """Validates that the data model does not exceed the maximum number of views.

    ## What it does
    This validator checks that the total number of views referenced by the data model
    does not exceed the limit defined in the CDF project.

    ## Why is this bad?
    CDF enforces limits on the number of views per data model to ensure optimal performance
    and resource utilization.

    ## Example
    If the CDF project has a limit of 100 views per data model, and the data model
    references 120 views, this validator will raise a ConsistencyError issue.

    """

    code = f"{BASE_CODE}-DATA-MODEL-001"

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


### View level limits


class ViewPropertyCountIsOutOfLimits(DataModelValidator):
    """Validates that a view does not exceed the maximum number of properties.

    ## What it does
    Checks that the view has no more properties than the CDF limit allows.

    ## Why is this bad?
    CDF enforces limits on the number of properties per view to ensure optimal performance.

    ## Example
    If a view has 150 properties and the CDF limit is 100 properties per view,
    this validator will raise a ConsistencyError issue.
    """

    code = f"{BASE_CODE}-VIEW-001"

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
        errors: list[ConsistencyError] = []
        merged_views = self.merged_views

        for view_ref in self.local_resources.views_by_reference.keys():
            view = merged_views.get(view_ref)
            if not view:
                raise RuntimeError(f"View {view_ref!s} not found in merged views. This is a bug!")

            if view.properties and len(view.properties) > self.limits.views.properties:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"View {view.as_reference()!s} has {len(view.properties)} properties,"
                            " which exceeds the limit of "
                            f"{self.limits.views.properties} properties per view."
                        ),
                        code=self.code,
                    )
                )

            elif not view.properties:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"View {view_ref!s} does "
                            "not have any properties defined, either directly or through implements."
                        ),
                        fix="Define at least one property for view",
                        code=self.code,
                    )
                )

        return errors


class ViewContainerCountIsOutOfLimits(DataModelValidator):
    """Validates that a view does not reference too many containers.

    ## What it does
    Checks that the view references no more containers than the CDF limit allows.

    ## Why is this bad?
    CDF enforces limits on the number of containers per view to prevent overly complex view definitions, leading
    to too many joins and performance degradation.

    ## Example
    If a view references 20 containers and the CDF limit is 10 containers per view,
    this validator will raise a ConsistencyError issue.
    """

    code = f"{BASE_CODE}-VIEW-002"

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
        errors: list[ConsistencyError] = []
        merged_views = self.merged_views

        # Single loop over all views
        for view_ref in self.local_resources.views_by_reference.keys():
            view = merged_views.get(view_ref)
            if not view:
                raise RuntimeError(f"View {view_ref!s} not found in merged views. This is a bug!")

            if view.properties:
                count = len(
                    {
                        prop.container
                        for prop in view.properties.values()
                        if (isinstance(prop, ViewCorePropertyRequest) and prop.container)
                    }
                )
                if count > self.limits.views.containers:
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

        return errors


class ViewImplementsCountIsOutOfLimits(DataModelValidator):
    """Validates that a view does not implement too many other views.

    ## What it does
    Checks that the view implements no more views than the CDF limit allows.

    ## Why is this bad?
    CDF enforces limits on the number of implemented views to prevent overly deep inheritance hierarchies.

    ## Example
    If a view implements 15 other views and the CDF limit is 10 implemented views per view,
    this validator will raise a ConsistencyError issue.
    """

    code = f"{BASE_CODE}-VIEW-003"

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
        errors: list[ConsistencyError] = []
        merged_views = self.merged_views

        # Single loop over all views
        for view_ref in self.local_resources.views_by_reference.keys():
            view = merged_views.get(view_ref)
            if not view:
                raise RuntimeError(f"View {view_ref!s} not found in merged views. This is a bug!")

            if view.implements and len(view.implements) > self.limits.views.implements:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"View {view_ref!s} implements {len(view.implements)} views,"
                            " which exceeds the limit of"
                            f" {self.limits.views.implements} implemented views per view."
                        ),
                        code=self.code,
                    )
                )
        return errors


### Container level limits


class ContainerPropertyCountIsOutOfLimits(DataModelValidator):
    """Validates that a container does not exceed the maximum number of properties.

    ## What it does
    Checks that the container has no more properties than the CDF limit allows.

    ## Why is this bad?
    CDF enforces limits on the number of properties per container to ensure optimal performance
    and prevent PostGres tables that have too many columns.

    ## Example
    If a container has 150 properties and the CDF limit is 100 properties per container,
    this validator will raise a ConsistencyError issue.
    """

    code = f"{BASE_CODE}-CONTAINER-001"

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
        errors: list[ConsistencyError] = []
        merged_containers = self.merged_containers

        # Single loop over all containers
        for container_ref in self.local_resources.containers_by_reference.keys():
            container = merged_containers.get(container_ref)
            if not container:
                raise RuntimeError(f"Container {container_ref!s} not found in merged containers. This is a bug!")

            if container.properties and len(container.properties) > self.limits.containers.properties():
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container {container.as_reference()!s} has {len(container.properties)} properties, "
                            "which exceeds the limit of "
                            f"{self.limits.containers.properties()} properties per container."
                        ),
                        fix="Define at least one property for container",
                        code=self.code,
                    )
                )
            elif not container.properties:
                errors.append(
                    ConsistencyError(
                        message=(f"Container {container.as_reference()!s} does not have any properties defined."),
                        fix="Define at least one property for container",
                        code=self.code,
                    )
                )

        return errors


class ContainerPropertyListSizeIsOutOfLimits(DataModelValidator):
    """Validates that container property list sizes do not exceed CDF limits.

    ## What it does
    Checks that list-type properties (max_list_size) do not exceed the appropriate limit based on:
    - Data type (Int32, Int64, DirectRelation, etc.)
    - Presence of btree index
    - Default vs maximum limits

    ## Why is this bad?
    CDF enforces different list size limits for different data types and indexing configurations
    to ensure optimal performance and prevent resource exhaustion.

    ## Example
    If a DirectRelation property has max_list_size=2000 with a btree index, but the limit
    is 1000 for indexed DirectRelations, this validator will raise a ConsistencyError issue.

    ## Note
    Enum properties are skipped as they have a separate 32-value limit checked during read time of data model to neat
    as a SyntaxError check.
    """

    code = f"{BASE_CODE}-CONTAINER-002"

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
        errors: list[ConsistencyError] = []
        merged_containers = self.merged_containers

        # Single loop over all containers
        for container_ref in self.local_resources.containers_by_reference.keys():
            container = merged_containers.get(container_ref)
            if not container:
                raise RuntimeError(f"Container {container_ref!s} not found in merged containers. This is a bug!")

            properties_by_index_type = self.container_property_by_index_type(container)

            for property_id, property_ in container.properties.items():
                type_ = property_.type

                # Skip enum properties (have separate 32-value limit)
                if isinstance(type_, EnumProperty):
                    continue

                # Only check listable properties with max_list_size set
                if not isinstance(type_, ListablePropertyTypeDefinition) or type_.max_list_size is None:
                    continue

                has_btree_index = property_id in properties_by_index_type[BtreeIndex.model_fields["index_type"].default]
                limit = self.limits.containers.properties.listable(type_, has_btree_index)

                if type_.max_list_size > limit:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"Container {container.as_reference()!s} has property {property_id} with list size "
                                f"{type_.max_list_size}, which exceeds the limit of {limit} "
                                f"for data type {type_.__class__.__name__}."
                            ),
                            code=self.code,
                        )
                    )

        return errors

    @staticmethod
    def container_property_by_index_type(container: ContainerRequest) -> dict[Literal["btree", "inverted"], list]:
        """Map container properties to their index types for limit validation.

        Categorizes container properties by their index configuration:
        - "btree": Properties with btree indexes (have stricter list size limits)
        - "inverted": Properties with inverted indexes

        This mapping is used to determine the appropriate list size limit for
        each property based on whether it has a btree index.

        Args:
            container: The container to analyze.

        Returns:
            Dictionary with index type strings as keys and lists of property identifiers
            as values. Returns empty lists for both index types if container has no indexes.
        """

        container_property_by_index_type: dict[Literal["btree", "inverted"], list] = {
            BtreeIndex.model_fields["index_type"].default: [],
            InvertedIndex.model_fields["index_type"].default: [],
        }
        if not container.indexes:
            return container_property_by_index_type

        for index in container.indexes.values():
            if isinstance(index, BtreeIndex):
                container_property_by_index_type[BtreeIndex.model_fields["index_type"].default].extend(index.properties)
            elif isinstance(index, InvertedIndex):
                container_property_by_index_type[InvertedIndex.model_fields["index_type"].default].extend(
                    index.properties
                )

        return container_property_by_index_type
