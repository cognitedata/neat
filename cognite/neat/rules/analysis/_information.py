import logging
import warnings
from typing import Any, cast

from pydantic import ValidationError

from cognite.neat.rules.models import SchemaCompleteness
from cognite.neat.rules.models._rdfpath import Hop, RDFPath, SingleProperty
from cognite.neat.rules.models.entities import ClassEntity, ReferenceEntity
from cognite.neat.rules.models.information import (
    InformationClass,
    InformationProperty,
    InformationRules,
)
from cognite.neat.utils.rdf_ import get_inheritance_path

from ._base import BaseAnalysis


class InformationAnalysis(BaseAnalysis[InformationRules, InformationClass, InformationProperty, ClassEntity, str]):
    """Assumes analysis over only the complete schema"""

    def _get_object(self, property_: InformationProperty) -> ClassEntity | None:
        return property_.value_type if isinstance(property_.value_type, ClassEntity) else None

    def _get_max_occurrence(self, property_: InformationProperty) -> int | float | None:
        return property_.max_count

    def _get_reference(self, class_or_property: InformationClass | InformationProperty) -> ReferenceEntity | None:
        return class_or_property.reference if isinstance(class_or_property.reference, ReferenceEntity) else None

    def _get_cls_entity(self, class_: InformationClass | InformationProperty) -> ClassEntity:
        return class_.class_

    @classmethod
    def _set_cls_entity(cls, property_: InformationProperty, class_: ClassEntity) -> None:
        property_.class_ = class_

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

    def has_hop_transformations(self):
        return any(
            prop_.transformation and isinstance(prop_.transformation.traversal, Hop) for prop_ in self.rules.properties
        )

    def define_property_renaming_config(self, class_: ClassEntity) -> dict[str, str]:
        property_renaming_configuration = {}

        if definitions := self.class_property_pairs(only_rdfpath=True, consider_inheritance=True).get(class_, None):
            for property_id, definition in definitions.items():
                if isinstance(
                    cast(RDFPath, definition.transformation).traversal,
                    SingleProperty,
                ):
                    graph_property = cast(
                        SingleProperty,
                        cast(RDFPath, definition.transformation).traversal,
                    ).property.suffix

                else:
                    graph_property = property_id

                property_renaming_configuration[graph_property] = property_id

        return property_renaming_configuration

    def subset_rules(self, desired_classes: set[ClassEntity]) -> InformationRules:
        """
        Subset rules to only include desired classes and their properties.

        Args:
            desired_classes: Desired classes to include in the reduced data model

        Returns:
            Instance of InformationRules

        !!! note "Inheritance"
            If desired classes contain a class that is a subclass of another class(es), the parent class(es)
            will be included in the reduced data model as well even though the parent class(es) are
            not in the desired classes set. This is to ensure that the reduced data model is
            consistent and complete.

        !!! note "Partial Reduction"
            This method does not perform checks if classes that are value types of desired classes
            properties are part of desired classes. If a class is not part of desired classes, but it
            is a value type of a property of a class that is part of desired classes, derived reduced
            rules will be marked as partial.

        !!! note "Validation"
            This method will attempt to validate the reduced rules with custom validations.
            If it fails, it will return a partial rules with a warning message, validated
            only with base Pydantic validators.
        """
        if self.rules.metadata.schema_ is not SchemaCompleteness.complete:
            raise ValueError("Rules are not complete cannot perform reduction!")
        class_as_dict = self.as_class_dict()
        class_parents_pairs = self.class_parent_pairs()
        defined_classes = self.defined_classes(consider_inheritance=True)

        possible_classes = defined_classes.intersection(desired_classes)
        impossible_classes = desired_classes - possible_classes

        # need to add all the parent classes of the desired classes to the possible classes
        parents: set[ClassEntity] = set()
        for class_ in possible_classes:
            parents = parents.union({parent for parent in get_inheritance_path(class_, class_parents_pairs)})
        possible_classes = possible_classes.union(parents)

        if not possible_classes:
            logging.error("None of the desired classes are defined in the data model!")
            raise ValueError("None of the desired classes are defined in the data model!")

        if impossible_classes:
            logging.warning(f"Could not find the following classes defined in the data model: {impossible_classes}")
            warnings.warn(
                f"Could not find the following classes defined in the data model: {impossible_classes}",
                stacklevel=2,
            )

        reduced_data_model: dict[str, Any] = {
            "metadata": self.rules.metadata.model_copy(),
            "prefixes": (self.rules.prefixes or {}).copy(),
            "classes": [],
            "properties": [],
        }

        logging.info(f"Reducing data model to only include the following classes: {possible_classes}")
        for class_ in possible_classes:
            reduced_data_model["classes"].append(class_as_dict[str(class_.suffix)])

        class_property_pairs = self.classes_with_properties(consider_inheritance=False)

        for class_, properties in class_property_pairs.items():
            if class_ in possible_classes:
                reduced_data_model["properties"].extend(properties)

        try:
            return type(self.rules)(**reduced_data_model)
        except ValidationError as e:
            warnings.warn(f"Reduced data model is not complete: {e}", stacklevel=2)
            reduced_data_model["metadata"].schema_ = SchemaCompleteness.partial
            return type(self.rules).model_construct(**reduced_data_model)
