from collections.abc import Iterable, Set
from typing import Literal

from cognite.neat.core._data_model.models import InformationRules, SheetList
from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._data_model.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    UnknownEntity,
)
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
        if self.join in ["primary", "combined"]:
            output = rules.model_copy(deep=True)
            secondary_classes = {cls.class_: cls for cls in self.secondary.classes}
            secondary_properties = {(prop.class_, prop.property_): prop for prop in self.secondary.properties}
        else:
            output = self.secondary.model_copy(deep=True)
            secondary_classes = {cls.class_: cls for cls in rules.classes}
            secondary_properties = {(prop.class_, prop.property_): prop for prop in rules.properties}

        merged_class_by_id = self._merge_classes(output.classes, secondary_classes)
        output.classes = SheetList[InformationClass](merged_class_by_id.values())

        merged_properties = self._merge_properties(
            output.properties, secondary_properties, set(merged_class_by_id.keys())
        )
        output.properties = SheetList[InformationProperty](merged_properties.values())

        return output

    def _merge_classes(
        self, primary_classes: Iterable[InformationClass], new_classes: dict[ClassEntity, InformationClass]
    ) -> dict[ClassEntity, InformationClass]:
        merged_classes = {cls.class_: cls for cls in primary_classes}
        for cls_, primary_cls in merged_classes.items():
            if cls_ not in new_classes:
                continue
            secondary_cls = new_classes[cls_]
            if self._swap_priority:
                primary_cls, secondary_cls = secondary_cls, primary_cls
            merged_cls = self.merge_classes(
                primary=primary_cls,
                secondary=secondary_cls,
                conflict_resolution=self.conflict_resolution,
            )
            merged_classes[cls_] = merged_cls

        if self.join == "combined":
            for cls_, secondary_cls in new_classes.items():
                if cls_ not in merged_classes:
                    merged_classes[cls_] = secondary_cls
        return merged_classes

    def _merge_properties(
        self,
        primary_properties: Iterable[InformationProperty],
        secondary_properties: dict[tuple[ClassEntity, str], InformationProperty],
        used_classes: Set[ClassEntity],
    ) -> dict[tuple[ClassEntity, str], InformationProperty]:
        merged_properties = {(prop.class_, prop.property_): prop for prop in primary_properties}
        for (cls_, prop_id), primary_property in merged_properties.items():
            if (cls_ not in used_classes) or (cls_, prop_id) not in secondary_properties:
                continue
            secondary_property = secondary_properties[(cls_, prop_id)]
            if self._swap_priority:
                primary_property, secondary_property = secondary_property, primary_property
            merged_property = self.merge_properties(
                primary=primary_property,
                secondary=secondary_property,
                conflict_resolution=self.conflict_resolution,
            )
            merged_properties[(cls_, prop_id)] = merged_property

        if self.join == "combined":
            for (cls_, prop_id), prop in secondary_properties.items():
                if (cls_, prop_id) not in merged_properties and cls_ in used_classes:
                    merged_properties[(cls_, prop_id)] = prop
        return merged_properties

    @property
    def _swap_priority(self) -> bool:
        return (self.priority == "secondary" and (self.join in ["primary", "combined"])) or (
            self.priority == "primary" and (self.join == "secondary")
        )

    @classmethod
    def merge_classes(
        cls,
        primary: InformationClass,
        secondary: InformationClass,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> InformationClass:
        # Combined = merge implements for both classes
        # Priority = keep the primary with fallback to secondary
        implements = (primary.implements or secondary.implements or []).copy()
        if conflict_resolution == "combined":
            seen = set(implements)
            for cls_ in secondary.implements or []:
                if cls_ not in seen:
                    seen.add(cls_)
                    implements.append(cls_)
        return InformationClass(
            neatId=primary.neatId,
            class_=primary.class_,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
            implements=implements,
            instance_source=primary.instance_source or secondary.instance_source,
            physical=primary.physical,
            conceptual=primary.conceptual,
        )

    @classmethod
    def merge_properties(
        cls,
        primary: InformationProperty,
        secondary: InformationProperty,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> InformationProperty:
        # Combined = merge value types and instance sources
        # Priority = keep the primary with fallback to secondary
        instance_source = (primary.instance_source or secondary.instance_source or []).copy()
        if conflict_resolution == "combined":
            seen = set(instance_source)
            for source in secondary.instance_source or []:
                if source not in seen:
                    seen.add(source)
                    instance_source.append(source)

        use_primary = conflict_resolution == "priority"
        return InformationProperty(
            neatId=primary.neatId,
            class_=primary.class_,
            property_=primary.property_,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
            min_count=primary.min_count
            if use_primary
            else cls._merge_min_count(primary.min_count, secondary.min_count),
            max_count=primary.max_count
            if use_primary
            else cls._merge_max_count(primary.max_count, secondary.max_count),
            default=primary.default or secondary.default,
            value_type=primary.value_type
            if use_primary
            else cls._merge_value_type(primary.value_type, secondary.value_type),
            instance_source=instance_source,
            inherited=primary.inherited,
            physical=primary.physical,
            conceptual=primary.conceptual,
        )

    @staticmethod
    def _merge_min_count(primary: int | None, secondary: int | None) -> int | None:
        if primary is None:
            return secondary
        if secondary is None:
            return primary
        return min(primary, secondary)

    @staticmethod
    def _merge_max_count(primary: int | float | None, secondary: int | float | None) -> int | float | None:
        if primary is None:
            return secondary
        if secondary is None:
            return primary
        output = max(primary, secondary)
        try:
            return int(output)
        except (OverflowError, ValueError):
            # The value is float('inf') or float('-inf')
            return output

    @staticmethod
    def _merge_value_type(
        primary: DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity,
        secondary: DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity,
    ) -> DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity:
        seen_types: set[DataType | ClassEntity] = set()
        ordered_types: list[DataType | ClassEntity] = []
        for type_ in (primary, secondary):
            if isinstance(type_, MultiValueTypeInfo):
                for t in type_.types:
                    if t not in seen_types:
                        seen_types.add(t)
                        ordered_types.append(t)
            elif isinstance(type_, ClassEntity):
                if type_ not in seen_types:
                    seen_types.add(type_)
                    ordered_types.append(type_)
            elif isinstance(type_, DataType):
                if type_ not in seen_types:
                    seen_types.add(type_)
                    ordered_types.append(type_)
            else:
                raise NotImplementedError(f"Unsupported type: {type_}")
        if len(ordered_types) == 1:
            return ordered_types[0]
        elif len(ordered_types) > 1:
            return MultiValueTypeInfo(types=ordered_types)
        else:
            return UnknownEntity()
