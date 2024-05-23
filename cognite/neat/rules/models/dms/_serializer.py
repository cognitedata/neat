from typing import Any, ClassVar, cast

from cognite.neat.rules.models import DMSRules
from cognite.neat.rules.models.dms import DMSContainer, DMSProperty, DMSView
from cognite.neat.rules.models.entities import ReferenceEntity, ViewEntity


class _DMSRulesSerializer:
    # These are the fields that need to be cleaned from the default space and version
    PROPERTIES_FIELDS: ClassVar[list[str]] = ["class_", "view", "value_type", "container"]
    VIEWS_FIELDS: ClassVar[list[str]] = ["class_", "view", "implements"]
    CONTAINERS_FIELDS: ClassVar[list[str]] = ["class_", "container"]

    def __init__(self, by_alias: bool, default_space: str, default_version: str) -> None:
        self.default_space = f"{default_space}:"
        self.default_version = f"version={default_version}"
        self.default_version_wrapped = f"({self.default_version})"

        self.properties_fields = self.PROPERTIES_FIELDS
        self.views_fields = self.VIEWS_FIELDS
        self.containers_fields = self.CONTAINERS_FIELDS
        self.prop_name = "properties"
        self.view_name = "views"
        self.container_name = "containers"
        self.metadata_name = "metadata"
        self.prop_view = "view"
        self.prop_container = "container"
        self.prop_view_property = "view_property"
        self.prop_value_type = "value_type"
        self.view_view = "view"
        self.view_implements = "implements"
        self.container_container = "container"
        self.container_constraint = "constraint"
        self.reference = "Reference" if by_alias else "reference"

        if by_alias:
            self.properties_fields = [
                DMSProperty.model_fields[field].alias or field for field in self.properties_fields
            ]
            self.views_fields = [DMSView.model_fields[field].alias or field for field in self.views_fields]
            self.containers_fields = [
                DMSContainer.model_fields[field].alias or field for field in self.containers_fields
            ]
            self.prop_view = DMSProperty.model_fields[self.prop_view].alias or self.prop_view
            self.prop_container = DMSProperty.model_fields[self.prop_container].alias or self.prop_container
            self.prop_view_property = DMSProperty.model_fields[self.prop_view_property].alias or self.prop_view_property
            self.prop_value_type = DMSProperty.model_fields[self.prop_value_type].alias or self.prop_value_type
            self.view_view = DMSView.model_fields[self.view_view].alias or self.view_view
            self.view_implements = DMSView.model_fields[self.view_implements].alias or self.view_implements
            self.container_container = (
                DMSContainer.model_fields[self.container_container].alias or self.container_container
            )
            self.container_constraint = (
                DMSContainer.model_fields[self.container_constraint].alias or self.container_constraint
            )
            self.prop_name = DMSRules.model_fields[self.prop_name].alias or self.prop_name
            self.view_name = DMSRules.model_fields[self.view_name].alias or self.view_name
            self.container_name = DMSRules.model_fields[self.container_name].alias or self.container_name
            self.metadata_name = DMSRules.model_fields[self.metadata_name].alias or self.metadata_name

    def clean(self, dumped: dict[str, Any], as_reference: bool) -> dict[str, Any]:
        # Sorting to get a deterministic order
        dumped[self.prop_name] = sorted(
            dumped[self.prop_name]["data"], key=lambda p: (p[self.prop_view], p[self.prop_view_property])
        )
        dumped[self.view_name] = sorted(dumped[self.view_name]["data"], key=lambda v: v[self.view_view])
        if container_data := dumped.get(self.container_name):
            dumped[self.container_name] = sorted(container_data["data"], key=lambda c: c[self.container_container])
        else:
            dumped.pop(self.container_name, None)

        for prop in dumped[self.prop_name]:
            if as_reference:
                view_entity = cast(ViewEntity, ViewEntity.load(prop[self.prop_view]))
                prop[self.reference] = str(
                    ReferenceEntity(
                        prefix=view_entity.prefix,
                        suffix=view_entity.suffix,
                        version=view_entity.version,
                        property=prop[self.prop_view_property],
                    )
                )
            for field_name in self.properties_fields:
                if as_reference and field_name == self.prop_container:
                    # When dumping as reference, the container should keep the default space for easy copying
                    # over to user sheets.
                    continue
                if value := prop.get(field_name):
                    prop[field_name] = value.removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
            # Value type can have a property as well
            prop[self.prop_value_type] = prop[self.prop_value_type].replace(self.default_version, "")

        for view in dumped[self.view_name]:
            if as_reference:
                view[self.reference] = view[self.view_view]
            for field_name in self.views_fields:
                if value := view.get(field_name):
                    view[field_name] = value.removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
            if value := view.get(self.view_implements):
                view[self.view_implements] = ",".join(
                    parent.strip().removeprefix(self.default_space).removesuffix(self.default_version_wrapped)
                    for parent in value.split(",")
                )

        for container in dumped.get(self.container_name, []):
            if as_reference:
                container[self.reference] = container[self.container_container]
            for field_name in self.containers_fields:
                if value := container.get(field_name):
                    container[field_name] = value.removeprefix(self.default_space)

            if value := container.get(self.container_constraint):
                container[self.container_constraint] = ",".join(
                    constraint.strip().removeprefix(self.default_space) for constraint in value.split(",")
                )
        return dumped
