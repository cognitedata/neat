import warnings
from typing import Any, cast

from pydantic import ValidationError
from rdflib import URIRef

from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models import SchemaCompleteness
from cognite.neat._rules.models._rdfpath import (
    Hop,
    RDFPath,
    SelfReferenceProperty,
    SingleProperty,
)
from cognite.neat._rules.models.entities import ClassEntity, ReferenceEntity
from cognite.neat._rules.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat._rules.models.information import (
    InformationClass,
    InformationProperty,
    InformationRules,
)
from cognite.neat._utils.collection_ import most_occurring_element
from cognite.neat._utils.rdf_ import get_inheritance_path

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

    def has_self_reference_property_transformations(self):
        return any(
            prop_.transformation and isinstance(prop_.transformation.traversal, SelfReferenceProperty)
            for prop_ in self.rules.properties
        )

    def all_reference_transformations(self):
        return [
            prop_
            for prop_ in self.rules.properties
            if prop_.transformation and isinstance(prop_.transformation.traversal, SelfReferenceProperty)
        ]

    def define_property_renaming_config(self, class_: ClassEntity) -> dict[str | URIRef, str]:
        property_renaming_configuration: dict[str | URIRef, str] = {}

        if definitions := self.class_property_pairs(only_rdfpath=True, consider_inheritance=True).get(class_, None):
            for property_id, definition in definitions.items():
                transformation = cast(RDFPath, definition.transformation)

                # use case we have a single property rdf path, and defined prefix
                # in either metadata or prefixes of rules
                if isinstance(
                    transformation.traversal,
                    SingleProperty,
                ) and (
                    transformation.traversal.property.prefix in self.rules.prefixes
                    or transformation.traversal.property.prefix == self.rules.metadata.prefix
                ):
                    namespace = (
                        self.rules.metadata.namespace
                        if transformation.traversal.property.prefix == self.rules.metadata.prefix
                        else self.rules.prefixes[transformation.traversal.property.prefix]
                    )

                    property_renaming_configuration[namespace[transformation.traversal.property.suffix]] = property_id

                # otherwise we default to the property id
                else:
                    property_renaming_configuration[property_id] = property_id

        return property_renaming_configuration

    def property_types(self, class_: ClassEntity) -> dict[str, EntityTypes]:
        property_types = {}
        if definitions := self.class_property_pairs(consider_inheritance=True).get(class_, None):
            for property_id, definition in definitions.items():
                property_types[property_id] = definition.type_

        return property_types

    def most_occurring_class_in_transformations(self, class_: ClassEntity) -> ClassEntity | None:
        classes = []
        if class_property_pairs := self.class_property_pairs(consider_inheritance=True, only_rdfpath=True).get(
            class_, None
        ):
            for property_ in class_property_pairs.values():
                classes.append(cast(RDFPath, property_.transformation).traversal.class_)

            return cast(ClassEntity, most_occurring_element(classes))
        else:
            return None

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
            raise ValueError("None of the desired classes are defined in the data model!")

        if impossible_classes:
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

    def class_uri(self, class_: ClassEntity) -> URIRef | None:
        """Get URI for a class entity based on the rules.

        Args:
            class_: instance of ClassEntity

        Returns:
            URIRef of the class entity or None if not found
        """

        # we need to handle optional renamings and we do this
        # by checking if the most occurring class in transformations alternatively
        # in cases when we are not specifying transformations we default to the class entity
        if not (most_frequent_class := self.most_occurring_class_in_transformations(class_)):
            most_frequent_class = class_

        # case 1 class prefix in rules.prefixes
        if most_frequent_class.prefix in self.rules.prefixes:
            return self.rules.prefixes[cast(str, most_frequent_class.prefix)][most_frequent_class.suffix]

        # case 2 class prefix equal to rules.metadata.prefix
        elif most_frequent_class.prefix == self.rules.metadata.prefix:
            return self.rules.metadata.namespace[most_frequent_class.suffix]

        # case 3 when class prefix is not found in prefixes of rules
        else:
            return None

    @property
    def multi_value_properties(self) -> list[InformationProperty]:
        return [prop_ for prop_ in self.rules.properties if isinstance(prop_.value_type, MultiValueTypeInfo)]
