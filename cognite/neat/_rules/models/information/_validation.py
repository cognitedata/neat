import itertools
from collections import Counter
from typing import cast

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError, ResourceNotDefinedError
from cognite.neat._issues.warnings._models import UndefinedClassWarning
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.entities import ClassEntity, UnknownEntity

from ._rules import InformationRules


class InformationPostValidation:
    """This class does all the validation of the Information rules that have dependencies
    between components."""

    def __init__(self, rules: InformationRules):
        self.rules = rules
        self.metadata = rules.metadata
        self.properties = rules.properties
        self.classes = rules.classes
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._namespaces_reassigned()
        self._classes_without_properties()
        self._parent_class_defined()
        self._referenced_classes_exist()
        self._referenced_value_types_exist()

        return self.issue_list

    def _classes_without_properties(self) -> None:
        # needs to be complete for this validation to pass
        defined_classes = {class_.class_ for class_ in self.classes}
        referred_classes = {property_.class_ for property_ in self.properties}
        class_parent_pairs = self._class_parent_pairs()

        if classes_without_properties := defined_classes.difference(referred_classes):
            for class_ in classes_without_properties:
                # USE CASE: class has no direct properties and no parents with properties
                # and it is a class in the prefix of data model, as long as it is in the
                # same prefix, meaning same space
                if not class_parent_pairs[class_] and class_.prefix == self.metadata.prefix:
                    self.issue_list.append(
                        ResourceNotDefinedError[ClassEntity](
                            resource_type="class",
                            identifier=class_,
                            location="Classes sheet",
                        )
                    )

    def _parent_class_defined(self) -> None:
        """This is a validation to check if the parent class of a class is defined in the classes sheet."""
        class_parent_pairs = self._class_parent_pairs()
        classes = set(class_parent_pairs.keys())
        parents = set(itertools.chain.from_iterable(class_parent_pairs.values()))

        if undefined_parents := parents.difference(classes):
            for parent in undefined_parents:
                if parent.prefix != self.metadata.prefix:
                    self.issue_list.append(UndefinedClassWarning(class_id=str(parent)))
                else:
                    self.issue_list.append(
                        ResourceNotDefinedError[ClassEntity](
                            resource_type="class",
                            identifier=parent,
                            location="Classes sheet",
                        )
                    )

    def _referenced_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        defined_classes = {class_.class_ for class_ in self.classes}
        classes_with_explicit_properties = {property_.class_ for property_ in self.properties}

        # USE CASE: models are complete
        if missing_classes := classes_with_explicit_properties.difference(defined_classes):
            for class_ in missing_classes:
                self.issue_list.append(
                    ResourceNotDefinedError[ClassEntity](
                        resource_type="class",
                        identifier=class_,
                        location="Classes sheet",
                    )
                )

    def _referenced_value_types_exist(self) -> None:
        # adding UnknownEntity to the set of defined classes to handle the case where a property references an unknown
        defined_classes = {class_.class_ for class_ in self.classes} | {UnknownEntity()}
        referred_object_types = {
            property_.value_type
            for property_ in self.rules.properties
            if property_.type_ == EntityTypes.object_property
        }

        if missing_value_types := referred_object_types.difference(defined_classes):
            # Todo: include row and column number
            for missing in missing_value_types:
                self.issue_list.append(
                    ResourceNotDefinedError[ClassEntity](
                        resource_type="class",
                        identifier=cast(ClassEntity, missing),
                        location="Classes sheet",
                    )
                )

    def _class_parent_pairs(self) -> dict[ClassEntity, list[ClassEntity]]:
        class_parent_pairs: dict[ClassEntity, list[ClassEntity]] = {}
        classes = self.rules.model_copy(deep=True).classes

        for class_ in classes:
            class_parent_pairs[class_.class_] = []
            if class_.implements is None:
                continue
            class_parent_pairs[class_.class_].extend(class_.implements)

        return class_parent_pairs

    def _namespaces_reassigned(self) -> None:
        prefixes = self.rules.prefixes.copy()
        prefixes[self.rules.metadata.namespace.prefix] = self.rules.metadata.namespace

        if len(set(prefixes.values())) != len(prefixes):
            reused_namespaces = [value for value, count in Counter(prefixes.values()).items() if count > 1]
            impacted_prefixes = [key for key, value in prefixes.items() if value in reused_namespaces]
            self.issue_list.append(
                NeatValueError(
                    "Namespace collision detected. The following prefixes "
                    f"are assigned to the same namespace: {impacted_prefixes}"
                    f"\nImpacted namespaces: {reused_namespaces}"
                    "\nMake sure that each unique namespace is assigned to a unique prefix"
                )
            )
