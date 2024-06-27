import itertools
import logging
import warnings
from collections import defaultdict
from typing import Any

import pandas as pd
from pydantic import ValidationError

from cognite.neat.rules.models import SchemaCompleteness
from cognite.neat.rules.models._rdfpath import RDFPath
from cognite.neat.rules.models.entities import ClassEntity, EntityTypes, ParentClassEntity, ReferenceEntity
from cognite.neat.rules.models.information import InformationClass, InformationProperty, InformationRules
from cognite.neat.utils.utils import get_inheritance_path

from ._base import BaseAnalysis


class InformationArchitectRulesAnalysis(BaseAnalysis):
    """Assumes analysis over only the complete schema"""

    def __init__(self, rules: InformationRules):
        self.rules = rules

    @property
    def directly_referred_classes(self) -> set[ClassEntity]:
        return {
            class_.reference.as_class_entity()
            for class_ in self.rules.classes
            if self.rules.reference
            and class_.reference
            and isinstance(class_.reference, ReferenceEntity)
            and class_.reference.prefix == self.rules.reference.metadata.prefix
        }

    @property
    def inherited_referred_classes(self) -> set[ClassEntity]:
        dir_referred_classes = self.directly_referred_classes
        inherited_referred_classes = []
        for class_ in dir_referred_classes:
            inherited_referred_classes.extend(self.class_inheritance_path(class_))
        return set(inherited_referred_classes)

    def class_parent_pairs(self) -> dict[ClassEntity, list[ParentClassEntity]]:
        """This only returns class - parent pairs only if parent is in the same data model"""
        class_subclass_pairs: dict[ClassEntity, list[ParentClassEntity]] = {}

        if not self.rules:
            return class_subclass_pairs

        for definition in self.rules.classes:
            class_subclass_pairs[definition.class_] = []

            if definition.parent is None:
                continue

            for parent in definition.parent:
                if parent.prefix == definition.class_.prefix:
                    class_subclass_pairs[definition.class_].append(parent)
                else:
                    warnings.warn(
                        f"Parent class {parent} of class {definition} is not in the same namespace, skipping !",
                        stacklevel=2,
                    )

        return class_subclass_pairs

    def classes_with_properties(
        self, consider_inheritance: bool = False
    ) -> dict[ClassEntity, list[InformationProperty]]:
        """Returns classes that have been defined in the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Dictionary of classes with a list of properties defined for them

        !!! note "consider_inheritance"
            If consider_inheritance is True, properties from parent classes will also be considered.
            This means if a class has a parent class, and the parent class has properties defined for it,
            while we do not have any properties defined for the child class, we will still consider the
            properties from the parent class. If consider_inheritance is False, we will only consider
            properties defined for the child class, thus if no properties are defined for the child class,
            it will not be included in the returned dictionary.
        """

        class_property_pairs: dict[ClassEntity, list[InformationProperty]] = defaultdict(list)

        for property_ in self.rules.properties:
            class_property_pairs[property_.class_].append(property_)

        if consider_inheritance:
            class_parent_pairs = self.class_parent_pairs()
            for class_ in class_parent_pairs:
                self._add_inherited_properties(class_, class_property_pairs, class_parent_pairs)

        return class_property_pairs

    def class_inheritance_path(self, class_: ClassEntity | str) -> list[ClassEntity]:
        class_ = class_ if isinstance(class_, ClassEntity) else ClassEntity.load(class_)
        class_parent_pairs = self.class_parent_pairs()
        return get_inheritance_path(class_, class_parent_pairs)

    @classmethod
    def _add_inherited_properties(
        cls,
        class_: ClassEntity,
        class_property_pairs: dict[ClassEntity, list[InformationProperty]],
        class_parent_pairs: dict[ClassEntity, list[ParentClassEntity]],
    ):
        inheritance_path = get_inheritance_path(class_, class_parent_pairs)
        for parent in inheritance_path:
            # ParentClassEntity -> ClassEntity to match the type of class_property_pairs
            if parent.as_class_entity() in class_property_pairs:
                for property_ in class_property_pairs[parent.as_class_entity()]:
                    property_ = property_.model_copy()

                    # This corresponds to importing properties from parent class
                    # making sure that the property is attached to desired child class
                    property_.class_ = class_
                    property_.inherited = True

                    # need same if we have RDF path to make sure that the starting class is the

                    if class_ in class_property_pairs:
                        class_property_pairs[class_].append(property_)
                    else:
                        class_property_pairs[class_] = [property_]

    def class_property_pairs(
        self, only_rdfpath: bool = False, consider_inheritance: bool = False
    ) -> dict[ClassEntity, dict[str, InformationProperty]]:
        """Returns a dictionary of classes with a dictionary of properties associated with them.

        Args:
            only_rdfpath : To consider only properties which have rule `rdfpath` set. Defaults False
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Dictionary of classes with a dictionary of properties associated with them.

        !!! note "difference to get_classes_with_properties"
            This method returns a dictionary of classes with a dictionary of properties associated with them.
            While get_classes_with_properties returns a dictionary of classes with a list of
            properties defined for them,
            here we filter the properties based on the `only_rdfpath` parameter and only consider
            the first definition of a property if it is defined more than once.

        !!! note "only_rdfpath"
            If only_rdfpath is True, only properties with RuleType.rdfpath will be returned as
            a part of the dictionary of properties related to a class. Otherwise, all properties
            will be returned.

        !!! note "consider_inheritance"
            If consider_inheritance is True, properties from parent classes will also be considered.
            This means if a class has a parent class, and the parent class has properties defined for it,
            while we do not have any properties defined for the child class, we will still consider the
            properties from the parent class. If consider_inheritance is False, we will only consider
            properties defined for the child class, thus if no properties are defined for the child class,
            it will not be included in the returned dictionary.
        """
        # TODO: https://cognitedata.atlassian.net/jira/software/projects/NEAT/boards/893?selectedIssue=NEAT-78

        class_property_pairs = {}

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

                if (only_rdfpath and isinstance(property_.transformation, RDFPath)) or not only_rdfpath:
                    processed_properties[property_.property_] = property_
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def class_linkage(self, consider_inheritance: bool = False) -> pd.DataFrame:
        """Returns a dataframe with the class linkage of the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Dataframe with the class linkage of the data model
        """

        class_linkage = pd.DataFrame(columns=["source_class", "target_class", "connecting_property", "max_occurrence"])

        class_property_pairs = self.classes_with_properties(consider_inheritance)
        properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

        for property_ in properties:
            if property_.type_ == EntityTypes.object_property:
                new_row = pd.Series(
                    {
                        "source_class": property_.class_,
                        "connecting_property": property_.property_,
                        "target_class": property_.value_type,
                        "max_occurrence": property_.max_count,
                    }
                )
                class_linkage = pd.concat([class_linkage, new_row.to_frame().T], ignore_index=True)

        class_linkage.drop_duplicates(inplace=True)
        class_linkage = class_linkage[["source_class", "connecting_property", "target_class", "max_occurrence"]]

        return class_linkage

    def connected_classes(self, consider_inheritance: bool = False) -> set[ClassEntity]:
        """Return a set of classes that are connected to other classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that are connected to other classes
        """
        class_linkage = self.class_linkage(consider_inheritance)
        return set(class_linkage.source_class.values).union(set(class_linkage.target_class.values))

    def defined_classes(self, consider_inheritance: bool = False) -> set[ClassEntity]:
        """Returns classes that have properties defined for them in the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that have been defined in the data model
        """
        class_property_pairs = self.classes_with_properties(consider_inheritance)
        properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

        return {property.class_ for property in properties}

    def disconnected_classes(self, consider_inheritance: bool = False) -> set[ClassEntity]:
        """Return a set of classes that are disconnected (i.e. isolated) from other classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that are disconnected from other classes
        """
        return self.defined_classes(consider_inheritance) - self.connected_classes(consider_inheritance)

    def symmetrically_connected_classes(
        self, consider_inheritance: bool = False
    ) -> set[tuple[ClassEntity, ClassEntity]]:
        """Returns a set of pairs of symmetrically linked classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of pairs of symmetrically linked classes

        !!! note "Symmetrically Connected Classes"
            Symmetrically connected classes are classes that are connected to each other
            in both directions. For example, if class A is connected to class B, and class B
            is connected to class A, then classes A and B are symmetrically connected.
        """

        # TODO: Find better name for this method
        sym_pairs: set[tuple[ClassEntity, ClassEntity]] = set()

        class_linkage = self.class_linkage(consider_inheritance)
        if class_linkage.empty:
            return sym_pairs

        for _, row in class_linkage.iterrows():
            source = row.source_class
            target = row.target_class
            target_targets = class_linkage[class_linkage.source_class == target].target_class.values
            if source in target_targets and (source, target) not in sym_pairs:
                sym_pairs.add((source, target))
        return sym_pairs

    def as_property_dict(
        self,
    ) -> dict[str, list[InformationProperty]]:
        """This is used to capture all definitions of a property in the data model."""
        property_dict: dict[str, list[InformationProperty]] = defaultdict(list)
        for definition in self.rules.properties:
            property_dict[definition.property_].append(definition)
        return property_dict

    def as_class_dict(self) -> dict[str, InformationClass]:
        """This is to simplify access to classes through dict."""
        class_dict: dict[str, InformationClass] = {}
        for definition in self.rules.classes:
            class_dict[str(definition.class_.suffix)] = definition
        return class_dict

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
            parents = parents.union(
                {parent.as_class_entity() for parent in get_inheritance_path(class_, class_parents_pairs)}
            )
        possible_classes = possible_classes.union(parents)

        if not possible_classes:
            logging.error("None of the desired classes are defined in the data model!")
            raise ValueError("None of the desired classes are defined in the data model!")

        if impossible_classes:
            logging.warning(f"Could not find the following classes defined in the data model: {impossible_classes}")
            warnings.warn(
                f"Could not find the following classes defined in the data model: {impossible_classes}", stacklevel=2
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
            return InformationRules(**reduced_data_model)
        except ValidationError as e:
            warnings.warn(f"Reduced data model is not complete: {e}", stacklevel=2)
            reduced_data_model["metadata"].schema_ = SchemaCompleteness.partial
            return InformationRules.model_construct(**reduced_data_model)
