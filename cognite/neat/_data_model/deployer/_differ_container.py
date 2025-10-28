from cognite.neat._data_model.models.dms import (
    ConstraintDefinition,
    ContainerPropertyDefinition,
    ContainerRequest,
    IndexDefinition,
)

from ._differ import ItemDiffer, diff_container
from .data_classes import (
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)


class ContainerDiffer(ItemDiffer[ContainerRequest]):
    def diff(self, cdf_container: ContainerRequest, container: ContainerRequest) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_container.name != container.name:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.SAFE,
                    field_path="name",
                    old_value=cdf_container.name,
                    new_value=container.name,
                )
            )

        if cdf_container.description != container.description:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.SAFE,
                    field_path="description",
                    old_value=cdf_container.description,
                    new_value=container.description,
                )
            )
        if cdf_container.used_for != container.used_for:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="usedFor",
                    old_value=cdf_container.used_for,
                    new_value=container.used_for,
                )
            )
        changes.extend(
            diff_container(
                "properties.",
                cdf_container.properties,
                container.properties,
                SeverityType.SAFE,
                SeverityType.BREAKING,
                ContainerPropertyDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that ConstraintDefinition and Constraint are compatible here
            diff_container(  # type: ignore[misc]
                "constraints.",
                cdf_container.constraints,
                container.constraints,
                SeverityType.SAFE,
                SeverityType.WARNING,
                ConstraintDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that IndexDefinition and Index are compatible here
            diff_container(  # type: ignore[misc]
                "indexes.",
                cdf_container.indexes,
                container.indexes,
                SeverityType.SAFE,
                SeverityType.WARNING,
                IndexDiffer(),
            )
        )

        return changes


class ContainerPropertyDiffer(ItemDiffer[ContainerPropertyDefinition]):
    def diff(
        self, cdf_property: ContainerPropertyDefinition, desired_property: ContainerPropertyDefinition
    ) -> list[PropertyChange]:
        raise NotImplementedError()


class ConstraintDiffer(ItemDiffer[ConstraintDefinition]):
    def diff(
        self, cdf_constraint: ConstraintDefinition, desired_constraint: ConstraintDefinition
    ) -> list[PropertyChange]:
        raise NotImplementedError()


class IndexDiffer(ItemDiffer[IndexDefinition]):
    def diff(self, cdf_index: IndexDefinition, desired_index: IndexDefinition) -> list[PropertyChange]:
        raise NotImplementedError()
