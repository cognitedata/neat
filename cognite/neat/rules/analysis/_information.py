from cognite.neat.rules.models.entities import ClassEntity, ReferenceEntity
from cognite.neat.rules.models.information import (
    InformationClass,
    InformationProperty,
    InformationRules,
)

from ._base import BaseAnalysis


class InformationAnalysis(BaseAnalysis[InformationRules, InformationClass, InformationProperty, ClassEntity, str]):
    """Assumes analysis over only the complete schema"""

    def _get_reference(self, class_or_property: InformationClass | InformationProperty) -> ReferenceEntity | None:
        return class_or_property.reference if isinstance(class_or_property.reference, ReferenceEntity) else None

    def _get_cls_entity(self, class_: InformationClass | InformationProperty) -> ClassEntity:
        return class_.class_

    def _get_prop_entity(self, property_: InformationProperty) -> str:
        return property_.property_

    def _get_cls_parents(self, class_: InformationClass) -> list[ClassEntity] | None:
        return list(class_.parent or []) or None

    def _get_reference_rules(self) -> InformationRules | None:
        return self.rules.reference

    def _get_properties(self) -> list[InformationProperty]:
        return list(self.rules.properties)

    def _get_classes(self) -> list[InformationClass]:
        return list(self.rules.classes)
