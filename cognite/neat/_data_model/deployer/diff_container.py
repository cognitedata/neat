from cognite.neat._data_model.models.dms import ContainerPropertyDefinition, ContainerRequest

from .data_classes import (
    AddedProperty,
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    RemovedProperty,
    SeverityType,
    T_Item,
)
from .diff import ResourceDiffer


class ContainerDiffer(ResourceDiffer[ContainerRequest]):
    def diff(self, cdf_container: ContainerRequest, container: ContainerRequest) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_container.name != container.name:
            changes.append(
                PrimitivePropertyChange(
                    item_severity="safe",
                    field_path="name",
                    old_value=cdf_container.name,
                    new_value=container.name,
                )
            )

        if cdf_container.description != container.description:
            changes.append(
                PrimitivePropertyChange(
                    item_severity="safe",
                    field_path="description",
                    old_value=cdf_container.description,
                    new_value=container.description,
                )
            )
        if cdf_container.used_for != container.used_for:
            changes.append(
                PrimitivePropertyChange(
                    item_severity="breaking",
                    field_path="usedFor",
                    old_value=cdf_container.used_for,
                    new_value=container.used_for,
                )
            )
        changes.extend(
            self._container_item(
                "properties.",
                cdf_container.properties,
                container.properties,
                "safe",
                "breaking",
                ContainerPropertyDiffer(),
            )
        )
        changes.extend(
            self._container_item("constraints.", cdf_container.constraints, container.constraints, "safe", "warning")
        )
        changes.extend(self._container_item("indexes.", cdf_container.indexes, container.indexes, "safe", "warning"))

        return changes

    def _container_item(
        self,
        parent_path: str,
        cdf_items: dict[str, T_Item],
        desired_items: dict[str, T_Item],
        add_severity: SeverityType,
        remove_severity: SeverityType,
        differ: ResourceDiffer[T_Item],
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        for key, desired_item in desired_items.items():
            item_path = f"{parent_path}{key}"
            if key not in cdf_items:
                changes.append(
                    AddedProperty(
                        item_severity=add_severity,
                        field_path=item_path,
                        new_value=desired_item,
                    )
                )
                continue
            cdf_item = cdf_items[key]
            diffs = differ.diff(cdf_item, desired_item)
            if diffs:
                changes.append(ContainerPropertyChange(field_path=item_path, changed_items=diffs))

        for key, cdf_item in cdf_items.items():
            if key not in desired_items:
                changes.append(
                    RemovedProperty(
                        item_severity=remove_severity,
                        field_path=f"{parent_path}{key}",
                        old_value=cdf_item,
                    )
                )
        return changes


class ContainerPropertyDiffer(ResourceDiffer[ContainerPropertyDefinition]):
    def diff(
        self, cdf_property: ContainerPropertyDefinition, desired_property: ContainerPropertyDefinition
    ) -> list[PropertyChange]:
        raise NotImplementedError()
