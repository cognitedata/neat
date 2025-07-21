from collections.abc import Iterable, Set
from typing import Literal

from cognite.neat.core._data_model.models import ConceptualDataModel, SheetList
from cognite.neat.core._data_model.models.conceptual import Concept, ConceptualProperty
from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._data_model.models.entities import (
    ConceptEntity,
    MultiValueTypeInfo,
    UnknownEntity,
)
from cognite.neat.core._data_model.transformers import VerifiedDataModelTransformer
from cognite.neat.core._issues.errors import NeatValueError


class MergeConceptualDataModel(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
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
            while if set to "combined", it will become a multivalued property.
    """

    def __init__(
        self,
        secondary: ConceptualDataModel,
        join: Literal["primary", "secondary", "combined"] = "combined",
        priority: Literal["primary", "secondary"] = "primary",
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> None:
        self.secondary = secondary
        self.join = join
        self.priority = priority
        self.conflict_resolution = conflict_resolution

    def transform(self, rules: ConceptualDataModel) -> ConceptualDataModel:
        primary_model = rules
        secondary_model = self.secondary
        if self.join == "secondary":
            primary_model, secondary_model = self.secondary, rules
        elif self.join not in ["primary", "combined"]:
            raise NeatValueError(
                f"Invalid join strategy: {self.join}. Must be one of ['primary', 'secondary', 'combined']"
            )
        output = primary_model.model_copy(deep=True)
        secondary_classes = {cls.concept: cls for cls in secondary_model.concepts}
        secondary_properties = {(prop.concept, prop.property_): prop for prop in secondary_model.properties}

        merged_concepts_by_id = self._merge_concepts(output.concepts, secondary_classes)
        output.concepts = SheetList[Concept](merged_concepts_by_id.values())

        merged_properties = self._merge_properties(
            output.properties, secondary_properties, set(merged_concepts_by_id.keys())
        )
        output.properties = SheetList[ConceptualProperty](merged_properties.values())

        return output

    def _merge_concepts(
        self, primary_classes: Iterable[Concept], new_classes: dict[ConceptEntity, Concept]
    ) -> dict[ConceptEntity, Concept]:
        merged_classes = {cls.concept: cls for cls in primary_classes}
        for cls_, primary_cls in merged_classes.items():
            if cls_ not in new_classes:
                continue
            secondary_cls = new_classes[cls_]
            if self._swap_priority:
                primary_cls, secondary_cls = secondary_cls, primary_cls
            merged_classes[cls_] = self.merge_classes(
                primary=primary_cls,
                secondary=secondary_cls,
                conflict_resolution=self.conflict_resolution,
            )

        if self.join == "combined":
            for cls_, secondary_cls in new_classes.items():
                if cls_ not in merged_classes:
                    merged_classes[cls_] = secondary_cls
        return merged_classes

    def _merge_properties(
        self,
        primary_properties: Iterable[ConceptualProperty],
        secondary_properties: dict[tuple[ConceptEntity, str], ConceptualProperty],
        used_classes: Set[ConceptEntity],
    ) -> dict[tuple[ConceptEntity, str], ConceptualProperty]:
        merged_properties = {(prop.concept, prop.property_): prop for prop in primary_properties}
        for (cls_, prop_id), primary_property in merged_properties.items():
            if (cls_ not in used_classes) or (cls_, prop_id) not in secondary_properties:
                continue
            secondary_property = secondary_properties[(cls_, prop_id)]
            if self._swap_priority:
                primary_property, secondary_property = secondary_property, primary_property
            merged_properties[(cls_, prop_id)] = self.merge_properties(
                primary=primary_property,
                secondary=secondary_property,
                conflict_resolution=self.conflict_resolution,
            )

        if self.join == "combined":
            for (cls_, prop_id), prop in secondary_properties.items():
                if (cls_, prop_id) not in merged_properties and cls_ in used_classes:
                    merged_properties[(cls_, prop_id)] = prop
        return merged_properties

    @property
    def _swap_priority(self) -> bool:
        """We swap the priority if 'join' and 'priority' are mismatched. For example, if
        we use a 'primary' join strategy, i.e., selecting classes from the primary model, but prioritize the
        secondary classes that matches the primary classes.
        """

        return (self.priority == "secondary" and (self.join in ["primary", "combined"])) or (
            self.priority == "primary" and (self.join == "secondary")
        )

    @classmethod
    def merge_classes(
        cls,
        primary: Concept,
        secondary: Concept,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> Concept:
        # Combined = merge implements for both classes
        # Priority = keep the primary with fallback to secondary
        implements = (primary.implements or secondary.implements or []).copy()
        if conflict_resolution == "combined":
            seen = set(implements)
            for cls_ in secondary.implements or []:
                if cls_ not in seen:
                    seen.add(cls_)
                    implements.append(cls_)
        return Concept(
            neatId=primary.neatId,
            concept=primary.concept,
            name=primary.name or secondary.name,
            description=primary.description or secondary.description,
            implements=implements,
            instance_source=primary.instance_source or secondary.instance_source,
            physical=primary.physical,
        )

    @classmethod
    def merge_properties(
        cls,
        primary: ConceptualProperty,
        secondary: ConceptualProperty,
        conflict_resolution: Literal["priority", "combined"] = "priority",
    ) -> ConceptualProperty:
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
        return ConceptualProperty(
            neatId=primary.neatId,
            concept=primary.concept,
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
            else cls.merge_value_type(primary.value_type, secondary.value_type),
            instance_source=instance_source,
            inherited=primary.inherited,
            physical=primary.physical,
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
    def merge_value_type(
        primary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
        secondary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
    ) -> DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity:
        # We use a set and list to preserve the order of the types
        # and to avoid duplicates
        seen_types: set[DataType | ConceptEntity] = set()
        ordered_types: list[DataType | ConceptEntity] = []
        for type_ in (primary, secondary):
            if isinstance(type_, UnknownEntity):
                # If any of the types is UnknownEntity, we return UnknownEntity
                return UnknownEntity()
            elif isinstance(type_, MultiValueTypeInfo):
                for t in type_.types:
                    if t not in seen_types:
                        seen_types.add(t)
                        ordered_types.append(t)
            elif isinstance(type_, ConceptEntity | DataType):
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
