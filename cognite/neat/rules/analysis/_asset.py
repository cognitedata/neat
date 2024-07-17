import warnings
from graphlib import TopologicalSorter
from typing import cast

from cognite.neat.rules.models import AssetRules
from cognite.neat.rules.models._rdfpath import RDFPath
from cognite.neat.rules.models.asset import AssetClass, AssetProperty
from cognite.neat.rules.models.entities import (
    AssetEntity,
    AssetFields,
    ClassEntity,
    EntityTypes,
    ReferenceEntity,
    RelationshipEntity,
)

from ._base import BaseAnalysis


class AssetAnalysis(BaseAnalysis[AssetRules, AssetClass, AssetProperty, ClassEntity, str]):
    """Assumes analysis over only the complete schema"""

    def _get_reference(self, class_or_property: AssetClass | AssetProperty) -> ReferenceEntity | None:
        return class_or_property.reference if isinstance(class_or_property.reference, ReferenceEntity) else None

    def _get_cls_entity(self, class_: AssetClass | AssetProperty) -> ClassEntity:
        return class_.class_

    def _get_prop_entity(self, property_: AssetProperty) -> str:
        return property_.property_

    def _get_cls_parents(self, class_: AssetClass) -> list[ClassEntity] | None:
        return list(class_.parent or []) or None

    def _get_reference_rules(self) -> AssetRules | None:
        return self.rules.reference

    @classmethod
    def _set_cls_entity(cls, property_: AssetProperty, class_: ClassEntity) -> None:
        property_.class_ = class_

    def _get_object(self, property_: AssetProperty) -> ClassEntity | None:
        return property_.value_type if isinstance(property_.value_type, ClassEntity) else None

    def _get_max_occurrence(self, property_: AssetProperty) -> int | float | None:
        return property_.max_count

    def _get_classes(self) -> list[AssetClass]:
        return list(self.rules.classes)

    def _get_properties(self) -> list[AssetProperty]:
        return list(self.rules.properties)

    def subset_rules(self, desired_classes: set[ClassEntity]) -> AssetRules:
        raise NotImplementedError("Method not implemented")

    def class_property_pairs(
        self,
        only_rdfpath: bool = False,
        consider_inheritance: bool = False,
        implementation_type: EntityTypes = EntityTypes.asset,
    ) -> dict[ClassEntity, dict[str, AssetProperty]]:
        class_property_pairs = {}

        T_implementation = AssetEntity if implementation_type == EntityTypes.asset else RelationshipEntity

        for class_, properties in self.classes_with_properties(consider_inheritance).items():
            processed_properties = {}
            for property_ in properties:
                if property_.property_ in processed_properties:
                    # TODO: use appropriate Warning class from _exceptions.py
                    # if missing make one !
                    warnings.warn(
                        f"Property {property_.property_} for {class_} has been defined more than once!"
                        " Only the first definition will be considered, skipping the rest..",
                        stacklevel=2,
                    )
                    continue

                if (
                    property_.implementation
                    and any(isinstance(implementation, T_implementation) for implementation in property_.implementation)
                    and (not only_rdfpath or (only_rdfpath and isinstance(property_.transformation, RDFPath)))
                ):
                    implementation = [
                        implementation
                        for implementation in property_.implementation
                        if isinstance(implementation, T_implementation)
                    ]

                    processed_properties[property_.property_] = property_.model_copy(
                        deep=True, update={"implementation": implementation}
                    )

            if processed_properties:
                class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def class_topological_sort(self) -> list[ClassEntity]:
        child_parent_asset: dict[ClassEntity, set] = {}
        defined_classes = set()
        for class_, properties in self.asset_definition().items():
            defined_classes.add(class_)
            for property_ in properties.values():
                if any(
                    cast(AssetEntity, implementation).property_ == AssetFields.parent_external_id
                    for implementation in property_.implementation
                ) and isinstance(property_.value_type, ClassEntity):
                    child_parent_asset[property_.class_] = {property_.value_type}

        ts = TopologicalSorter(child_parent_asset)

        # attempt to sort the classes in topological order + the rest of the classes
        if child_parent_asset:
            ordered_classes = list(ts.static_order())
            return ordered_classes + list(defined_classes - set(ordered_classes))

        # all asset types are root assets and have no parent
        else:
            return list(defined_classes)

    def asset_definition(
        self, only_rdfpath: bool = False, consider_inheritance: bool = False
    ) -> dict[ClassEntity, dict[str, AssetProperty]]:
        return self.class_property_pairs(
            consider_inheritance=consider_inheritance,
            only_rdfpath=only_rdfpath,
            implementation_type=EntityTypes.asset,
        )

    def relationship_definition(
        self, only_rdfpath: bool = False, consider_inheritance: bool = False
    ) -> dict[ClassEntity, dict[str, AssetProperty]]:
        return self.class_property_pairs(
            consider_inheritance=consider_inheritance,
            only_rdfpath=only_rdfpath,
            implementation_type=EntityTypes.relationship,
        )

    def define_property_renaming_config(self, class_: ClassEntity) -> dict[str, str]:
        property_renaming_configuration = {}

        if asset_definition := self.asset_definition().get(class_, None):
            for property_, transformation in asset_definition.items():
                asset_property = cast(list[AssetEntity], transformation.implementation)[0].property_

                if asset_property != "metadata":
                    property_renaming_configuration[property_] = str(asset_property)
                else:
                    property_renaming_configuration[property_] = f"{asset_property}.{property_}"

        return property_renaming_configuration
