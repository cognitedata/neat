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


class UnionConceptualDataModel(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
    """Takes the union two conceptual models.
    Args:
        primary: The primary model to merge with the secondary model given in the transform method.
    """

    def __init__(self, primary: ConceptualDataModel) -> None:
        self.primary = primary

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        primary_model = self.primary
        secondary_model = data_model

        output = primary_model.model_copy(deep=True)
        secondary_classes = {cls.concept: cls for cls in secondary_model.concepts}
        secondary_properties = {(prop.concept, prop.property_): prop for prop in secondary_model.properties}

        union_concepts_by_id = self._union_concepts(output.concepts, secondary_classes)
        output.concepts = SheetList[Concept](union_concepts_by_id.values())

        union_properties = self._union_properties(
            output.properties, secondary_properties, set(union_concepts_by_id.keys())
        )
        output.properties = SheetList[ConceptualProperty](union_properties.values())

        return output

    def _union_concepts(
        self, primary_concepts: Iterable[Concept], new_concepts: dict[ConceptEntity, Concept]
    ) -> dict[ConceptEntity, Concept]:
        union_classes = {cls.concept: cls for cls in primary_concepts}
        for concept, primary_concept in union_classes.items():
            if concept not in new_concepts:
                continue
            secondary_concept = new_concepts[concept]
            union_classes[concept] = self.union_concepts(
                primary=primary_concept,
                secondary=secondary_concept,
                conflict_resolution="combined",
            )

        for concept, secondary_concept in new_concepts.items():
            if concept not in union_classes:
                union_classes[concept] = secondary_concept
        return union_classes

    def _union_properties(
        self,
        primary_properties: Iterable[ConceptualProperty],
        secondary_properties: dict[tuple[ConceptEntity, str], ConceptualProperty],
        used_concepts: Set[ConceptEntity],
    ) -> dict[tuple[ConceptEntity, str], ConceptualProperty]:
        union_properties = {(prop.concept, prop.property_): prop for prop in primary_properties}
        for (concept, prop_id), primary_property in union_properties.items():
            if (concept not in used_concepts) or (concept, prop_id) not in secondary_properties:
                continue
            secondary_property = secondary_properties[(concept, prop_id)]
            union_properties[(concept, prop_id)] = self.union_properties(
                primary=primary_property,
                secondary=secondary_property,
                conflict_resolution="combined",
            )

        for (concept, prop_id), prop in secondary_properties.items():
            if (concept, prop_id) not in union_properties and concept in used_concepts:
                union_properties[(concept, prop_id)] = prop
        return union_properties

    @classmethod
    def union_concepts(
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
    def union_properties(
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
            else cls._union_min_count(primary.min_count, secondary.min_count),
            max_count=primary.max_count
            if use_primary
            else cls._union_max_count(primary.max_count, secondary.max_count),
            default=primary.default or secondary.default,
            value_type=primary.value_type
            if use_primary
            else cls.union_value_type(primary.value_type, secondary.value_type),
            instance_source=instance_source,
            inherited=primary.inherited,
            physical=primary.physical,
        )

    @staticmethod
    def _union_min_count(primary: int | None, secondary: int | None) -> int | None:
        if primary is None:
            return secondary
        if secondary is None:
            return primary
        return min(primary, secondary)

    @staticmethod
    def _union_max_count(primary: int | float | None, secondary: int | float | None) -> int | float | None:
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
    def union_value_type(
        primary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
        secondary: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity,
    ) -> DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity:
        # We use a set and list to preserve the order of the types
        # and to avoid duplicates
        seen_types: set[DataType | ConceptEntity] = set()
        ordered_types: list[DataType | ConceptEntity] = []
        for type_ in (primary, secondary):
            if isinstance(type_, UnknownEntity):
                # If any of the types is UnknownEntity, we skip it.
                continue
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
        if len(ordered_types) == 0:
            return UnknownEntity()
        if len(ordered_types) == 1:
            return ordered_types[0]
        else:  # len(ordered_types) > 1:
            return MultiValueTypeInfo(types=ordered_types)
