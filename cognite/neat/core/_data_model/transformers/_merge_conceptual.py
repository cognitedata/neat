from typing import Literal

from cognite.neat.core._data_model.models import InformationRules
from cognite.neat.core._data_model.models.information import InformationClass, InformationProperty
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer


class MergeInformationRules(VerifiedRulesTransformer[InformationRules, InformationRules]):
    """Merges two conceptual models into one.

    Args:
        secondary: The secondary model. The primary model is the one that is passed to the transform method.
        join: The join strategy for merging classes. To only keep classes from the primary model, use "primary".
            To only keep classes from the secondary model, use "secondary". To keep all classes, use "combined".
        priority: For properties that exist in both models, the priority determines which model's property is kept.
            For example, if 'name' of a property exists in both models, and the priority is set to "primary",
            the property from the primary model will be kept.
        conflict_resolution: Applies to properties that can be combined. For example, if a property exists in both model
            with different value types, then, if set to "priority", the model with the higher priority will be kept,
            while if set to "combined", it will become a multi-valued property.
    """

    def __init__(
        self,
        secondary: InformationRules,
        join: Literal["primary", "secondary", "combined"] = "combined",
        priority: Literal["primary", "secondary"] = "primary",
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> None:
        self.secondary = secondary
        self.join = join
        self.priority = priority
        self.conflict_resolution = conflict_resolution

    def transform(self, rules: InformationRules) -> InformationRules:
        output = rules.model_copy(deep=True)
        existing_classes = {cls.class_ for cls in output.classes}
        for cls in self.secondary.classes:
            if cls.class_ not in existing_classes:
                output.classes.append(cls)
        existing_properties = {(prop.class_, prop.property_) for prop in output.properties}
        for prop in self.secondary.properties:
            if (prop.class_, prop.property_) not in existing_properties:
                output.properties.append(prop)
        for prefix, namespace in self.secondary.prefixes.items():
            if prefix not in output.prefixes:
                output.prefixes[prefix] = namespace
        return output

    @classmethod
    def merge_classes(
        cls,
        primary: InformationClass,
        secondary: InformationClass,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> InformationClass:
        raise NotImplementedError()

    @classmethod
    def merge_properties(
        cls,
        primary: InformationProperty,
        secondary: InformationProperty,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> InformationProperty:
        raise NotImplementedError()
