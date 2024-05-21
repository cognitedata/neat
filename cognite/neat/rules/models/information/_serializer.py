from typing import Any, ClassVar

from cognite.neat.rules.models import InformationRules
from cognite.neat.rules.models.entities import ClassEntity, ReferenceEntity
from cognite.neat.rules.models.information import InformationClass, InformationProperty


class _InformationRulesSerializer:
    # These are the fields that need to be cleaned from the default space and version
    PROPERTIES_FIELDS: ClassVar[list[str]] = ["class_", "value_type"]
    CLASSES_FIELDS: ClassVar[list[str]] = ["class_"]

    def __init__(self, by_alias: bool, default_prefix: str) -> None:
        self.default_prefix = f"{default_prefix}:"

        self.properties_fields = self.PROPERTIES_FIELDS
        self.classes_fields = self.CLASSES_FIELDS

        self.prop_name = "properties"
        self.class_name = "classes"
        self.metadata_name = "metadata"
        self.class_parent = "parent"

        self.prop_property = "property_"
        self.prop_class = "class_"

        self.reference = "Reference" if by_alias else "reference"
        if by_alias:
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

    def clean(self, dumped: dict[str, Any], as_reference: bool) -> dict[str, Any]:
        # Sorting to get a deterministic order
        dumped[self.prop_name] = sorted(
            dumped[self.prop_name]["data"], key=lambda p: (p[self.prop_class], p[self.prop_property])
        )
        dumped[self.class_name] = sorted(dumped[self.class_name]["data"], key=lambda v: v[self.prop_class])

        for prop in dumped[self.prop_name]:
            if as_reference:
                class_entity = ClassEntity.load(prop[self.prop_class])
                prop[self.reference] = str(
                    ReferenceEntity(
                        prefix=str(class_entity.prefix), suffix=class_entity.suffix, property=prop[self.prop_property]
                    )
                )

            for field_name in self.properties_fields:
                if value := prop.get(field_name):
                    prop[field_name] = value.removeprefix(self.default_prefix)

        for class_ in dumped[self.class_name]:
            if as_reference:
                class_[self.reference] = class_[self.prop_class]
            for field_name in self.classes_fields:
                if value := class_.get(field_name):
                    class_[field_name] = value.removeprefix(self.default_prefix)

            if value := class_.get(self.class_parent):
                class_[self.class_parent] = ",".join(
                    parent.strip().removeprefix(self.default_prefix) for parent in value.split(",")
                )

        return dumped
