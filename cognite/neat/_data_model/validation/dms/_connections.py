"""Validators for connections in data model specifications."""

from dataclasses import dataclass

from cognite.neat._data_model.models.dms._data_types import DirectNodeRelation
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError, Recommendation

BASE_CODE = "NEAT-DMS-CONNECTIONS"


class ConnectionValueTypeUnexisting(DataModelValidator):
    """Validates that connection value types exist.

    ## What it does
    Validates that all connection value types defined in the data model exist.

    ## Why is this bad?
    If a connection value type does not exist, the data model cannot be deployed to CDF.
    This means that the connection will not be able to function.

    ## Example
    If view WindTurbine has a connection property windFarm with value type WindFarm, but WindFarm view is not defined,
    the data model cannot be deployed to CDF.
    """

    code = f"{BASE_CODE}-001"

    def run(self) -> list[ConsistencyError]:
        undefined_value_types = []

        for (view, property_), value_type in self.local_resources.connection_end_node_types.items():
            if value_type is None:
                continue

            if value_type in self.local_resources.views_by_reference:
                continue

            if (
                self.modus_operandi == "additive" or value_type.space != self.local_resources.data_model_reference.space
            ) and value_type in self.cdf_resources.views_by_reference:
                continue

            undefined_value_types.append((view, property_, value_type))

        return [
            ConsistencyError(
                message=(
                    f"View {view!s} connection {property_!s} has value type {value_type!s} "
                    "which is not defined as a view in the data model neither exists in CDF."
                ),
                fix="Define necessary view",
                code=self.code,
            )
            for (view, property_, value_type) in undefined_value_types
        ]


class ConnectionValueTypeUndefined(DataModelValidator):
    """Validates that connection value types are not None, i.e. undefined.

    ## What it does
    Validates that connections have explicitly defined value types (i.e., end connection node type).

    ## Why is this bad?
    If a connection value type is None (undefined), there is no type information about the end node of the connection.
    This yields an ambiguous data model definition, which may lead to issues during consumption of data from CDF.

    ## Example
    Consider a scenario where we have views WindTurbine,ArrayCable and Substation. Lets say WindTurbine has a connection
    `connectsTo` with value type None (undefined), then it is unclear what type of view the connection points to as
    both ArrayCable and Substation are valid targets for the connection.

    """

    code = f"{BASE_CODE}-002"

    def run(self) -> list[Recommendation]:
        missing_value_types = []

        for (view, property_), value_type in self.local_resources.connection_end_node_types.items():
            if not value_type:
                missing_value_types.append((view, property_))

        return [
            Recommendation(
                message=(
                    f"View {view!s} connection {property_!s} is missing value type (end node type)."
                    " This yields ambiguous data model definition."
                ),
                fix="Define necessary value type",
                code=self.code,
            )
            for (view, property_) in missing_value_types
        ]


@dataclass
class ReverseConnectionContext:
    """Context for validating a bidirectional connection.
    This context holds all necessary references to validate the connection.

    Attributes:
        target_view_ref: Reference to the target view containing the reverse property.
        reverse_property: Identifier of the reverse property in the target view.
        through: Direct reference defining the direct property used in the reverse connection.
        source_view_ref: Reference to the source view containing the direct property, to which the reverse points.


    Example:
        View `WindTurbine` has property `windFarm` (direct) → points to View `WindFarm`
        View `WindFarm` has property `turbines` (reverse) → points to View `WindTurbine` through `WindTurbine.windFarm`
    """

    target_view_ref: ViewReference
    reverse_property: str
    through: ViewDirectReference
    source_view_ref: ViewReference


def _normalize_through_reference(
    source_view_ref: ViewReference, through: ContainerDirectReference | ViewDirectReference
) -> ViewDirectReference:
    """Normalize through reference to ViewDirectReference for consistent processing."""
    if isinstance(through, ContainerDirectReference):
        return ViewDirectReference(source=source_view_ref, identifier=through.identifier)
    return through


class ReverseConnectionSourceViewMissing(DataModelValidator):
    """Validates that source view referenced in reverse connection exist.

    ## What it does
    Checks that the source view used to configure a reverse connection exists.

    ## Why is this bad?
    A reverse connection requires a corresponding direct connection in the source view.
    If the source view doesn't exist, the reverse connection is invalid.

    ## Example
    If WindFarm has a reverse property `turbines` through `WindTurbine.windFarm`,
    but WindTurbine view doesn't exist, the reverse connection cannot function.
    """

    code = f"{BASE_CODE}-REVERSE-001"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} used to configure reverse connection "
                            f"'{reverse_prop_name}' in target view {target_view_ref!s} "
                            "does not exist in the data model or CDF."
                        ),
                        fix="Define the missing source view",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionSourcePropertyMissing(DataModelValidator):
    """Validates that source property referenced in reverse connections exist.

    ## What it does
    Checks that the direct connection property in the source view (used in the reverse connection's 'through')
    actually exists in the source view.

    ## Why is this bad?
    A reverse connection requires a corresponding direct connection property in the source view.
    If this property doesn't exist, the bidirectional connection is incomplete.

    ## Example
    If WindFarm has a reverse property `turbines` through `WindTurbine.windFarm`,
    but WindTurbine view doesn't have a `windFarm` property, the reverse connection is invalid.
    """

    code = f"{BASE_CODE}-REVERSE-002"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view:
                continue  # Handled by ReverseConnectionSourceViewMissing

            if not source_view.properties or through.identifier not in source_view.properties:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} is missing property '{through.identifier}' "
                            f"which is required to configure the reverse connection "
                            f"'{reverse_prop_name}' in target view {target_view_ref!s}."
                        ),
                        fix="Add the missing property to the source view",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionSourcePropertyWrongType(DataModelValidator):
    """Validates that source property for the reverse connections is a direct relation.

    ## What it does
    Checks that the property referenced in a reverse connection's 'through' clause
    is actually a direct connection property (not a primitive or other type).

    ## Why is this bad?
    Reverse connections can only work with direct connection properties.
    Using other property types breaks the bidirectional relationship.

    ## Example
    If WindFarm has a reverse property `turbines` through `WindTurbine.name`,
    but `name` is a Text property (not a direct connection), the reverse connection is invalid.
    """

    code = f"{BASE_CODE}-REVERSE-003"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property:
                continue  # Handled by ReverseConnectionSourcePropertyMissing

            if not isinstance(source_property, ViewCorePropertyRequest):
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Source view {source_view_ref!s} property '{through.identifier}' "
                            f"used for configuring the reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s} is not a direct connection property."
                        ),
                        fix="Update view property to be a direct connection property",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionContainerMissing(DataModelValidator):
    """Validates that the container referenced by the reverse connection source properties exist.

    ## What it does
    Checks that the container holding the direct connection property (used in reverse connection) exists.

    ## Why is this bad?
    The direct connection property must be stored in a container.
    If the container doesn't exist, the connection cannot be persisted.

    ## Example
    If WindTurbine.windFarm maps to container `WindTurbine`, but this container doesn't exist,
    the reverse connection from WindFarm cannot function.
    """

    code = f"{BASE_CODE}-REVERSE-004"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            container_ref = source_property.container
            container_property_id = source_property.container_property_identifier

            source_container = self._select_container_with_property(container_ref, container_property_id)
            if not source_container:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} is missing in both the data model and CDF. "
                            f"This container is required by view {source_view_ref!s}"
                            f" property '{through.identifier}', "
                            f"which configures the reverse connection '{reverse_prop_name}'"
                            f" in target view {target_view_ref!s}."
                        ),
                        fix="Define the missing container",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionContainerPropertyMissing(DataModelValidator):
    """Validates that container property referenced by the reverse connections exists.

    ## What it does
    Checks that the property in the container (mapped from the view's direct connection property)
    actually exists in the container.

    ## Why is this bad?
    The view property must map to an actual container property for data persistence.
    If the container property doesn't exist, data cannot be stored.

    ## Example
    If WindTurbine.windFarm maps to container property `WindTurbine.windFarm`,
    but this container property doesn't exist, the connection cannot be stored.
    """

    code = f"{BASE_CODE}-REVERSE-005"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            container_ref = source_property.container
            container_property_id = source_property.container_property_identifier

            source_container = self._select_container_with_property(container_ref, container_property_id)
            if not source_container:
                continue  # Handled by ReverseConnectionContainerMissing

            if not source_container.properties or container_property_id not in source_container.properties:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container {container_ref!s} is missing property '{container_property_id}'. "
                            f"This property is required by the source view {source_view_ref!s}"
                            f" property '{through.identifier}', "
                            f"which configures the reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s}."
                        ),
                        fix="Add the missing property to the container",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionContainerPropertyWrongType(DataModelValidator):
    """Validates that the container property used in reverse connection is the direct relations.

    ## What it does
    Checks that the container property (mapped from view's direct connection property)
    has type DirectNodeRelation.

    ## Why is this bad?
    Container properties backing connection view properties must be DirectNodeRelation type.
    Other types cannot represent connections in the underlying storage.

    ## Example
    If WindTurbine.windFarm maps to container property with type Text instead of DirectNodeRelation,
    the connection cannot be stored correctly.
    """

    code = f"{BASE_CODE}-REVERSE-006"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            container_ref = source_property.container
            container_property_id = source_property.container_property_identifier

            source_container = self._select_container_with_property(container_ref, container_property_id)
            if not source_container or not source_container.properties:
                continue  # Handled by other validators

            container_property = source_container.properties.get(container_property_id)
            if not container_property:
                continue  # Handled by ReverseConnectionContainerPropertyMissing

            if not isinstance(container_property.type, DirectNodeRelation):
                errors.append(
                    ConsistencyError(
                        message=(
                            f"Container property '{container_property_id}' in container {container_ref!s} "
                            f"must be a direct connection, but found type '{container_property.type!s}'. "
                            f"This property is used by source view {source_view_ref!s} property '{through.identifier}' "
                            f"to configure reverse connection '{reverse_prop_name}' in target view {target_view_ref!s}."
                        ),
                        fix="Change container property type to be a direct connection",
                        code=self.code,
                    )
                )

        return errors


class ReverseConnectionTargetMissing(DataModelValidator):
    """Validates that the direct connection in reverse connection pair have target views specified.

    ## What it does
    Checks whether the direct connection property (referenced by reverse connection) has a value type.

    ## Why is this bad?
    While CDF allows value type None as a SEARCH hack for multi-value relations,
    it's better to explicitly specify the target view for clarity and maintainability.

    ## Example
    If WindTurbine.windFarm has value type None instead of WindFarm,
    this validator recommends specifying WindFarm explicitly.
    """

    code = f"{BASE_CODE}-REVERSE-007"

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            actual_target_view = source_property.source

            if not actual_target_view:
                recommendations.append(
                    Recommendation(
                        message=(
                            f"Source view {source_view_ref!s} property '{through.identifier}' "
                            f"has no target view specified (value type is None). "
                            f"This property is used for reverse connection '{reverse_prop_name}' "
                            f"in target view {target_view_ref!s}. "
                            f"While this works as a hack for multi-value relations in CDF Search, "
                            f"it's recommended to explicitly define the target view as {target_view_ref!s}."
                        ),
                        fix="Set the property's value type to the target view for better clarity",
                        code=self.code,
                    )
                )

        return recommendations


class ReverseConnectionPointsToAncestor(DataModelValidator):
    """Validates that direct connections point to specific views rather than ancestors.

    ## What it does
    Checks whether the direct connection property points to an ancestor of the expected target view
    and recommends pointing to the specific target instead.

    ## Why is this bad?
    While technically valid, pointing to ancestors can be confusing and may lead to mistakes.
    It's clearer to point to the specific target view.

    ## Example
    If WindFarm.turbines expects WindTurbine.windFarm to point to WindFarm,
    but it points to Asset (ancestor of WindFarm), this validator recommends the change.
    """

    code = f"{BASE_CODE}-REVERSE-008"

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            actual_target_view = source_property.source

            if not actual_target_view:
                continue  # Handled by ReverseConnectionTargetMissing

            if self._is_ancestor_of_target(actual_target_view, target_view_ref):
                recommendations.append(
                    Recommendation(
                        message=(
                            f"The direct connection property '{through.identifier}' in view {source_view_ref!s} "
                            f"configures the reverse connection '{reverse_prop_name}' in {target_view_ref!s}. "
                            f"Therefore, it is expected that '{through.identifier}' points to {target_view_ref!s}. "
                            f"However, it currently points to {actual_target_view!s}, which is an ancestor of "
                            f"{target_view_ref!s}. "
                            "While this will allow for model to be valid, it can be a source of confusion and mistakes."
                        ),
                        fix="Update the direct connection property to point to the target view instead of its ancestor",
                        code=self.code,
                    )
                )

        return recommendations


class ReverseConnectionTargetMismatch(DataModelValidator):
    """Validates that direct connections point to the correct target views.

    ## What it does
    Checks that the direct connection property points to the expected target view
    (the view containing the reverse connection).

    ## Why is this bad?
    The reverse connection expects a bidirectional relationship.
    If the direct connection points to a different view, the relationship is broken.

    ## Example
    If WindFarm.turbines is a reverse through WindTurbine.windFarm,
    but WindTurbine.windFarm points to SolarFarm instead of WindFarm, the connection is invalid.
    """

    code = f"{BASE_CODE}-REVERSE-009"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        for (target_view_ref, reverse_prop_name), (
            source_view_ref,
            through,
        ) in self.local_resources.reverse_to_direct_mapping.items():
            through = _normalize_through_reference(source_view_ref, through)
            source_view = self._select_view_with_property(source_view_ref, through.identifier)

            if not source_view or not source_view.properties:
                continue  # Handled by other validators

            source_property = source_view.properties.get(through.identifier)
            if not source_property or not isinstance(source_property, ViewCorePropertyRequest):
                continue  # Handled by other validators

            actual_target_view = source_property.source

            if not actual_target_view:
                continue  # Handled by ReverseConnectionTargetMissing

            if self._is_ancestor_of_target(actual_target_view, target_view_ref):
                continue  # Handled by ReverseConnectionTargetAncestor

            if actual_target_view != target_view_ref:
                errors.append(
                    ConsistencyError(
                        message=(
                            f"The reverse connection '{reverse_prop_name}' in view {target_view_ref!s} "
                            f"expects its corresponding direct connection in view {source_view_ref!s} "
                            f"(property '{through.identifier}') to point back to {target_view_ref!s}, "
                            f"but it actually points to {actual_target_view!s}."
                        ),
                        fix="Update the direct connection property to point back to the correct target view",
                        code=self.code,
                    )
                )

        return errors
