import itertools
from typing import cast

from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._base import DataModelType, SchemaCompleteness
from cognite.neat.rules.models.entities import ClassEntity, EntityTypes, UnknownEntity
from cognite.neat.utils.utils import get_inheritance_path

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

        if dangling_classes:
            self.issue_list.append(
                issues.spreadsheet.ClassNoPropertiesNoParentError([class_.versioned_id for class_ in dangling_classes])
            )

    def _referenced_parent_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        class_parent_pairs = self._class_parent_pairs()
        classes = set(class_parent_pairs.keys())
        parents = set(itertools.chain.from_iterable(class_parent_pairs.values()))

        if undefined_parents := parents.difference(classes):
            self.issue_list.append(
                issues.spreadsheet.ParentClassesNotDefinedError([missing.versioned_id for missing in undefined_parents])
            )

    def _referenced_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        defined_classes = {class_.class_ for class_ in self.classes}
        referred_classes = {property_.class_ for property_ in self.properties}

        # USE CASE: models are complete
        if self.metadata.schema_ == SchemaCompleteness.complete and (
            missing_classes := referred_classes.difference(defined_classes)
        ):
            self.issue_list.append(
                issues.spreadsheet.PropertiesDefinedForUndefinedClassesError(
                    [missing.versioned_id for missing in missing_classes]
                )
            )

        # USE CASE: models are extended (user + last = complete)
        if self.metadata.schema_ == SchemaCompleteness.extended:
            defined_classes |= {class_.class_ for class_ in cast(InformationRules, self.rules.last).classes}
            if missing_classes := referred_classes.difference(defined_classes):
                self.issue_list.append(
                    issues.spreadsheet.PropertiesDefinedForUndefinedClassesError(
                        [missing.versioned_id for missing in missing_classes]
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
            self.issue_list.append(
                issues.spreadsheet.ValueTypeNotDefinedError(
                    [cast(ClassEntity, missing).versioned_id for missing in missing_value_types]
                )
            )

        # USE CASE: models are extended (user + last = complete)
        if self.metadata.schema_ == SchemaCompleteness.extended:
            defined_classes |= {class_.class_ for class_ in cast(InformationRules, self.rules.last).classes}
            if missing_value_types := referred_object_types.difference(defined_classes):
                self.issue_list.append(
                    issues.spreadsheet.ValueTypeNotDefinedError(
                        [cast(ClassEntity, missing).versioned_id for missing in missing_value_types]
                    )
                )

    def _class_parent_pairs(self) -> dict[ClassEntity, list[ClassEntity]]:
        class_subclass_pairs: dict[ClassEntity, list[ClassEntity]] = {}

        classes = self.rules.model_copy(deep=True).classes.data

        # USE CASE: Solution model being extended (user + last + reference = complete)
        if (
            self.metadata.schema_ == SchemaCompleteness.extended
            and self.metadata.data_model_type == DataModelType.solution
        ):
            classes += (
                cast(InformationRules, self.rules.last).model_copy(deep=True).classes.data
                + cast(InformationRules, self.rules.reference).model_copy(deep=True).classes.data
            )

        # USE CASE: Solution model being created from scratch (user + reference = complete)
        elif (
            self.metadata.schema_ == SchemaCompleteness.complete
            and self.metadata.data_model_type == DataModelType.solution
        ):
            classes += cast(InformationRules, self.rules.reference).model_copy(deep=True).classes.data

        # USE CASE: Enterprise model being extended (user + last = complete)
        elif (
            self.metadata.schema_ == SchemaCompleteness.extended
            and self.metadata.data_model_type == DataModelType.enterprise
        ):
            classes += cast(InformationRules, self.rules.last).model_copy(deep=True).classes.data

        for class_ in classes:
            class_subclass_pairs[class_.class_] = []
            if class_.parent is None:
                continue
            class_subclass_pairs[class_.class_].extend([parent.as_class_entity() for parent in class_.parent])

        return class_subclass_pairs
