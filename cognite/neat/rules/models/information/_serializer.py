from typing import Any, ClassVar, cast

from pydantic_core.core_schema import SerializationInfo

from cognite.neat.rules.models import InformationRules
from cognite.neat.rules.models.information import InformationClass, InformationProperty


class _InformationRulesSerializer:
    # These are the fields that need to be cleaned from the default space and version
    PROPERTIES_FIELDS: ClassVar[list[str]] = ["class_", "value_type"]
    CLASSES_FIELDS: ClassVar[list[str]] = ["class_"]

    def __init__(self, info: SerializationInfo, default_prefix: str) -> None:
        self.default_prefix = f"{default_prefix}:"

        self.properties_fields = self.PROPERTIES_FIELDS
        self.classes_fields = self.CLASSES_FIELDS

        self.prop_name = "properties"
        self.class_name = "classes"
        self.metadata_name = "metadata"
        self.class_parent = "parent"

        self.prop_property = "property_"
        self.prop_class = "class_"

        if info.by_alias:
            self.properties_fields = [
                InformationProperty.model_fields[field].alias or field for field in self.properties_fields
            ]
            self.classes_fields = [InformationClass.model_fields[field].alias or field for field in self.classes_fields]
            self.prop_name = InformationRules.model_fields[self.prop_name].alias or self.prop_name
            self.class_name = InformationRules.model_fields[self.class_name].alias or self.class_name
            self.class_parent = InformationClass.model_fields[self.class_parent].alias or self.class_parent
            self.metadata_name = InformationRules.model_fields[self.metadata_name].alias or self.metadata_name

            self.prop_property = InformationProperty.model_fields[self.prop_property].alias or self.prop_property
            self.prop_class = InformationProperty.model_fields[self.prop_class].alias or self.prop_class

        if isinstance(info.exclude, dict):
            # Just for happy mypy
            exclude = cast(dict, info.exclude)
            self.metadata_exclude = exclude.get("metadata", set()) or set()
            self.exclude_classes = exclude.get("classes", {}).get("__all__", set()) or set()
            self.exclude_properties = exclude.get("properties", {}).get("__all__", set())
            self.exclude_top = {k for k, v in exclude.items() if not v}
        else:
            self.exclude_top = set(info.exclude or {})
            self.exclude_properties = set()
            self.exclude_classes = set()
            self.metadata_exclude = set()

    def clean(self, dumped: dict[str, Any]) -> dict[str, Any]:
        # Sorting to get a deterministic order
        dumped[self.prop_name] = sorted(
            dumped[self.prop_name]["data"], key=lambda p: (p[self.prop_class], p[self.prop_property])
        )
        dumped[self.class_name] = sorted(dumped[self.class_name]["data"], key=lambda v: v[self.prop_class])

        for prop in dumped[self.prop_name]:
            for field_name in self.properties_fields:
                if value := prop.get(field_name):
                    prop[field_name] = value.removeprefix(self.default_prefix)

            if self.exclude_properties:
                for field in self.exclude_properties:
                    prop.pop(field, None)

        for class_ in dumped[self.class_name]:
            for field_name in self.classes_fields:
                if value := class_.get(field_name):
                    class_[field_name] = value.removeprefix(self.default_prefix)

            if value := class_.get(self.class_parent):
                class_[self.class_parent] = ",".join(
                    parent.strip().removeprefix(self.default_prefix) for parent in value.split(",")
                )

        if self.metadata_exclude:
            for field in self.metadata_exclude:
                dumped[self.metadata_name].pop(field, None)
        for field in self.exclude_top:
            dumped.pop(field, None)
        return dumped
