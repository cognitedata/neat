import warnings

from cognite.neat.rules.models import AssetRules
from cognite.neat.rules.models._rdfpath import RDFPath
from cognite.neat.rules.models.asset import AssetClass, AssetProperty
from cognite.neat.rules.models.entities import AssetEntity, ClassEntity, EntityTypes, RelationshipEntity

from ._base import BaseAnalysis


class AssetAnalysis(BaseAnalysis[AssetRules, AssetClass, AssetProperty, ClassEntity, str]):
    """Assumes analysis over only the complete schema"""

    def _get_classes(self) -> list[AssetClass]:
        return list(self.rules.classes)

    def _get_properties(self) -> list[AssetProperty]:
        return list(self.rules.properties)

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
