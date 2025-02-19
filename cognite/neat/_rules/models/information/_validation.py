import itertools
from collections import Counter, defaultdict

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.errors._resources import (
    ResourceDuplicatedError,
    ResourceNotDefinedError,
)
from cognite.neat._issues.warnings._models import UndefinedClassWarning
from cognite.neat._issues.warnings._resources import (
    ResourceNotDefinedWarning,
    ResourceRegexViolationWarning,
)
from cognite.neat._rules._constants import PATTERNS, EntityTypes
from cognite.neat._rules.models.entities import ClassEntity, UnknownEntity
from cognite.neat._rules.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat._utils.spreadsheet import SpreadsheetRead
from cognite.neat._utils.text import humanize_collection

from ._rules import InformationRules


class InformationValidation:
    """This class does all the validation of the Information rules that have dependencies
    between components."""

    def __init__(self, rules: InformationRules, read_info_by_spreadsheet: dict[str, SpreadsheetRead] | None = None):
        self.rules = rules
        self._read_info_by_spreadsheet = read_info_by_spreadsheet or {}
        self._metadata = rules.metadata
        self._properties = rules.properties
        self._classes = rules.classes
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._duplicated_resources()
        self._namespaces_reassigned()
        self._classes_without_properties()
        self._undefined_classes()
        self._parent_class_defined()
        self._referenced_classes_exist()
        self._referenced_value_types_exist()
        self._regex_compliance_with_dms()

        return self.issue_list

    def _duplicated_resources(self) -> None:
        properties_sheet = self._read_info_by_spreadsheet.get("Properties")
        classes_sheet = self._read_info_by_spreadsheet.get("Classes")

        visited = defaultdict(list)
        for row_no, property_ in enumerate(self._properties):
            visited[property_._identifier()].append(
                properties_sheet.adjusted_row_number(row_no) if properties_sheet else row_no + 1
            )

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            self.issue_list.append(
                ResourceDuplicatedError(
                    identifier[1],
                    "property",
                    (
                        "the Properties sheet at row "
                        f"{humanize_collection(rows)}"
                        " if data model is read from a spreadsheet."
                    ),
                )
            )

        visited = defaultdict(list)
        for row_no, class_ in enumerate(self._classes):
            visited[class_._identifier()].append(
                classes_sheet.adjusted_row_number(row_no) if classes_sheet else row_no + 1
            )

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            self.issue_list.append(
                ResourceDuplicatedError(
                    identifier[0],
                    "class",
                    (f"the Classes sheet at row {humanize_collection(rows)} if data model is read from a spreadsheet."),
                )
            )

    def _classes_without_properties(self) -> None:
        defined_classes = {class_.class_ for class_ in self._classes}
        referred_classes = {property_.class_ for property_ in self._properties}
        class_parent_pairs = self._class_parent_pairs()

        if classes_without_properties := defined_classes.difference(referred_classes):
            for class_ in classes_without_properties:
                # USE CASE: class has no direct properties and no parents with properties
                # and it is a class in the prefix of data model, as long as it is in the
                # same prefix, meaning same space
                if not class_parent_pairs[class_] and class_.prefix == self._metadata.prefix:
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="class",
                            identifier=class_,
                            location="Properties sheet",
                        )
                    )

    def _undefined_classes(self) -> None:
        defined_classes = {class_.class_ for class_ in self._classes}
        referred_classes = {property_.class_ for property_ in self._properties}

        if undefined_classes := referred_classes.difference(defined_classes):
            for class_ in undefined_classes:
                self.issue_list.append(
                    ResourceNotDefinedError(
                        identifier=class_,
                        resource_type="class",
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
                if parent.prefix != self._metadata.prefix:
                    self.issue_list.append(UndefinedClassWarning(class_id=str(parent)))
                else:
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="class",
                            identifier=parent,
                            location="Classes sheet",
                        )
                    )

    def _referenced_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        defined_classes = {class_.class_ for class_ in self._classes}
        classes_with_explicit_properties = {property_.class_ for property_ in self._properties}

        # USE CASE: models are complete
        if missing_classes := classes_with_explicit_properties.difference(defined_classes):
            for class_ in missing_classes:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="class",
                        identifier=class_,
                        location="Classes sheet",
                    )
                )

    def _referenced_value_types_exist(self) -> None:
        # adding UnknownEntity to the set of defined classes to handle the case where a property references an unknown
        defined_classes = {class_.class_ for class_ in self._classes} | {UnknownEntity()}
        referred_object_types = {
            property_.value_type
            for property_ in self.rules.properties
            if property_.type_ == EntityTypes.object_property
        }

        if missing_value_types := referred_object_types.difference(defined_classes):
            # Todo: include row and column number
            for missing in missing_value_types:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="class",
                        identifier=missing,
                        location="Classes sheet",
                    )
                )

    def _regex_compliance_with_dms(self) -> None:
        """Check regex compliance with DMS of properties, classes and value types."""

        for prop_ in self._properties:
            if not PATTERNS.dms_property_id_compliance.match(prop_.property_):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        prop_.property_,
                        "Property",
                        "Properties sheet, Property column",
                        PATTERNS.dms_property_id_compliance.pattern,
                    )
                )
            if not PATTERNS.view_id_compliance.match(prop_.class_.suffix):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        prop_.class_,
                        "Class",
                        "Properties sheet, Class column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            # Handling Value Type
            if (
                isinstance(prop_.value_type, ClassEntity)
                and prop_.value_type != UnknownEntity()
                and not PATTERNS.view_id_compliance.match(prop_.value_type.suffix)
            ):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        prop_.value_type,
                        "Value Type",
                        "Properties sheet, Value Type column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )
            if isinstance(prop_.value_type, MultiValueTypeInfo):
                for value_type in prop_.value_type.types:
                    if (
                        isinstance(prop_.value_type, ClassEntity)
                        and prop_.value_type != UnknownEntity()
                        and not PATTERNS.view_id_compliance.match(value_type.suffix)
                    ):
                        self.issue_list.append(
                            ResourceRegexViolationWarning(
                                value_type,
                                "Value Type",
                                "Properties sheet, Value Type column",
                                PATTERNS.view_id_compliance.pattern,
                            )
                        )

        for class_ in self._classes:
            if not PATTERNS.view_id_compliance.match(class_.class_.suffix):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        class_.class_,
                        "Class",
                        "Classes sheet, Class column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            if class_.implements:
                for parent in class_.implements:
                    if not PATTERNS.view_id_compliance.match(parent.suffix):
                        self.issue_list.append(
                            ResourceRegexViolationWarning(
                                parent,
                                "Class",
                                "Classes sheet, Implements column",
                                PATTERNS.view_id_compliance.pattern,
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
