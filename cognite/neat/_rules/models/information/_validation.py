import itertools
from collections import Counter
from typing import cast

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError, ResourceNotDefinedError
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models._base_rules import DataModelType, SchemaCompleteness
from cognite.neat._rules.models.entities import ClassEntity, UnknownEntity
from cognite.neat._utils.rdf_ import get_inheritance_path

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
        if self.metadata.schema_ == SchemaCompleteness.partial:
            return self.issue_list

        if self.metadata.data_model_type == DataModelType.solution and not self.rules.reference:
            raise ValueError("Reference data model is missing")

        if self.metadata.schema_ == SchemaCompleteness.extended and not self.rules.last:
            raise ValueError("Last version is missing")

        self._dangling_classes()
        self._referenced_parent_classes_exist()
        self._referenced_classes_exist()
        self._referenced_value_types_exist()
        self._namespaces_reassigned()

        return self.issue_list

    def _dangling_classes(self) -> None:
        # needs to be complete for this validation to pass
        defined_classes = {class_.class_ for class_ in self.classes}
        referred_classes = {property_.class_ for property_ in self.properties}
        class_parent_pairs = self._class_parent_pairs()
        dangling_classes = set()

        if classes_without_properties := defined_classes.difference(referred_classes):
            for class_ in classes_without_properties:
                # USE CASE: class has no direct properties and no parents
                if class_ not in class_parent_pairs:
                    dangling_classes.add(class_)
                # USE CASE: class has no direct properties and no parents with properties
                elif class_ not in class_parent_pairs and not any(
                    parent in referred_classes for parent in get_inheritance_path(class_, class_parent_pairs)
                ):
                    dangling_classes.add(class_)

        for class_ in dangling_classes:
            self.issue_list.append(
                NeatValueError(f"Class {class_} has no properties and is not a parent of any class with properties")
            )

    def _referenced_parent_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        class_parent_pairs = self._class_parent_pairs()
        classes = set(class_parent_pairs.keys())
        parents = set(itertools.chain.from_iterable(class_parent_pairs.values()))

        if undefined_parents := parents.difference(classes):
            for parent in undefined_parents:
                # Todo: include row and column number
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
        referred_classes = {property_.class_ for property_ in self.properties}

        # USE CASE: models are complete
        if self.metadata.schema_ == SchemaCompleteness.complete and (
            missing_classes := referred_classes.difference(defined_classes)
        ):
            for class_ in missing_classes:
                self.issue_list.append(
                    ResourceNotDefinedError[ClassEntity](
                        resource_type="class",
                        identifier=class_,
                        location="Classes sheet",
                    )
                )

        # USE CASE: models are extended (user + last = complete)
        if self.metadata.schema_ == SchemaCompleteness.extended:
            defined_classes |= {class_.class_ for class_ in cast(InformationRules, self.rules.last).classes}
            if missing_classes := referred_classes.difference(defined_classes):
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

        # USE CASE: models are complete
        if self.metadata.schema_ == SchemaCompleteness.complete and (
            missing_value_types := referred_object_types.difference(defined_classes)
        ):
            # Todo: include row and column number
            for missing in missing_value_types:
                self.issue_list.append(
                    ResourceNotDefinedError[ClassEntity](
                        resource_type="class",
                        identifier=cast(ClassEntity, missing),
                        location="Classes sheet",
                    )
                )

        # USE CASE: models are extended (user + last = complete)
        if self.metadata.schema_ == SchemaCompleteness.extended:
            defined_classes |= {class_.class_ for class_ in cast(InformationRules, self.rules.last).classes}
            if missing_value_types := referred_object_types.difference(defined_classes):
                # Todo: include row and column number
                for missing in missing_value_types:
                    self.issue_list.append(
                        ResourceNotDefinedError(
                            resource_type="class",
                            identifier=cast(ClassEntity, missing),
                            location="Classes sheet",
                        )
                    )

    def _class_parent_pairs(self) -> dict[ClassEntity, list[ClassEntity]]:
        class_subclass_pairs: dict[ClassEntity, list[ClassEntity]] = {}

        classes = self.rules.model_copy(deep=True).classes

        # USE CASE: Solution model being extended (user + last + reference = complete)
        if (
            self.metadata.schema_ == SchemaCompleteness.extended
            and self.metadata.data_model_type == DataModelType.solution
        ):
            classes += (
                cast(InformationRules, self.rules.last).model_copy(deep=True).classes
                + cast(InformationRules, self.rules.reference).model_copy(deep=True).classes
            )

        # USE CASE: Solution model being created from scratch (user + reference = complete)
        elif (
            self.metadata.schema_ == SchemaCompleteness.complete
            and self.metadata.data_model_type == DataModelType.solution
        ):
            classes += cast(InformationRules, self.rules.reference).model_copy(deep=True).classes

        # USE CASE: Enterprise model being extended (user + last = complete)
        elif (
            self.metadata.schema_ == SchemaCompleteness.extended
            and self.metadata.data_model_type == DataModelType.enterprise
        ):
            classes += cast(InformationRules, self.rules.last).model_copy(deep=True).classes

        for class_ in classes:
            class_subclass_pairs[class_.class_] = []
            if class_.parent is None:
                continue
            class_subclass_pairs[class_.class_].extend(class_.parent)

        return class_subclass_pairs

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
