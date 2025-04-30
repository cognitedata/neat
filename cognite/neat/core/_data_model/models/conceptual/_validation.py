import itertools
from collections import Counter, defaultdict

from cognite.neat.core._data_model._constants import PATTERNS, EntityTypes
from cognite.neat.core._data_model.models.entities import ConceptEntity, UnknownEntity
from cognite.neat.core._data_model.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat.core._issues import IssueList
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._issues.errors._resources import (
    ResourceDuplicatedError,
    ResourceNotDefinedError,
)
from cognite.neat.core._issues.warnings._models import UndefinedClassWarning
from cognite.neat.core._issues.warnings._resources import (
    ResourceNotDefinedWarning,
    ResourceRegexViolationWarning,
)
from cognite.neat.core._utils.spreadsheet import SheetRowTracker
from cognite.neat.core._utils.text import humanize_collection

from ._validated_data_model import ConceptualDataModel


class ConceptualValidation:
    """This class does all the validation of the conceptual data model have dependencies
    between components."""

    def __init__(
        self,
        data_model: ConceptualDataModel,
        sheet_row_tracker_by_sheet: dict[str, SheetRowTracker] | None = None,
    ):
        self.data_model = data_model
        self.sheet_row_tracker_by_sheet = sheet_row_tracker_by_sheet or {}
        self._metadata = data_model.metadata
        self._properties = data_model.properties
        self._concepts = data_model.concepts
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._duplicated_resources()
        self._namespaces_reassigned()
        self._concepts_without_properties()
        self._undefined_concepts()
        self._parent_concept_defined()
        self._referenced_concepts_exist()
        self._referenced_value_types_exist()
        self._physical_regex_compliance()

        return self.issue_list

    def _duplicated_resources(self) -> None:
        properties_sheet_row_tracker = self.sheet_row_tracker_by_sheet.get("Properties")
        classes_sheet_row_tracker = self.sheet_row_tracker_by_sheet.get("Classes")

        visited = defaultdict(list)
        for row_no, property_ in enumerate(self._properties):
            visited[property_._identifier()].append(
                properties_sheet_row_tracker.adjusted_row_number(row_no)
                if properties_sheet_row_tracker
                else row_no + 1
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
        for row_no, class_ in enumerate(self._concepts):
            visited[class_._identifier()].append(
                classes_sheet_row_tracker.adjusted_row_number(row_no)
                if classes_sheet_row_tracker
                else row_no + 1
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

    def _concepts_without_properties(self) -> None:
        defined_concepts = {concept.concept for concept in self._concepts}
        referred_concepts = {property_.concept for property_ in self._properties}
        parent_concepts_by_children = self._parent_concepts_by_children()

        if concepts_without_properties := defined_concepts.difference(
            referred_concepts
        ):
            for concept in concepts_without_properties:
                # USE CASE: class has no direct properties and no parents with properties
                # and it is a class in the prefix of data model, as long as it is in the
                # same prefix, meaning same space
                if (
                    not parent_concepts_by_children[concept]
                    and concept.prefix == self._metadata.prefix
                ):
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="concept",
                            identifier=concept,
                            location="Properties sheet",
                        )
                    )

    def _undefined_concepts(self) -> None:
        defined_concepts = {concept.concept for concept in self._concepts}
        referred_concepts = {property_.concept for property_ in self._properties}

        if undefined_concepts := referred_concepts.difference(defined_concepts):
            for concept in undefined_concepts:
                self.issue_list.append(
                    ResourceNotDefinedError(
                        identifier=concept,
                        resource_type="concept",
                        location="Concepts sheet",
                    )
                )

    def _parent_concept_defined(self) -> None:
        """This is a validation to check if the parent concept is defined in the Concepts sheet."""
        parent_concepts_by_children = self._parent_concepts_by_children()
        concepts = set(parent_concepts_by_children.keys())
        parents = set(
            itertools.chain.from_iterable(parent_concepts_by_children.values())
        )

        if undefined_parents := parents.difference(concepts):
            for parent in undefined_parents:
                if parent.prefix != self._metadata.prefix:
                    self.issue_list.append(UndefinedClassWarning(class_id=str(parent)))
                else:
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="concept",
                            identifier=parent,
                            location="Concepts sheet",
                        )
                    )

    def _referenced_concepts_exist(self) -> None:
        # needs to be complete for this validation to pass
        defined_concepts = {concept.concept for concept in self._concepts}
        concepts_with_explicit_properties = {
            property_.concept for property_ in self._properties
        }

        # USE CASE: models are complete
        if missing_concepts := concepts_with_explicit_properties.difference(
            defined_concepts
        ):
            for concept in missing_concepts:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=concept,
                        location="Concepts sheet",
                    )
                )

    def _referenced_value_types_exist(self) -> None:
        # adding UnknownEntity to the set of defined classes to handle the case where a property references an unknown
        defined_concepts = {concept.concept for concept in self._concepts} | {
            UnknownEntity()
        }
        referred_object_types = {
            property_.value_type
            for property_ in self.data_model.properties
            if property_.type_ == EntityTypes.object_property
        }

        if missing_value_types := referred_object_types.difference(defined_concepts):
            # Todo: include row and column number
            for missing in missing_value_types:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=missing,
                        location="Concepts sheet",
                    )
                )

    def _physical_regex_compliance(self) -> None:
        """Check regex compliance with physical data model external ids."""

        for prop_ in self._properties:
            if not PATTERNS.physical_property_id_compliance.match(prop_.property_):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        prop_.property_,
                        "Property",
                        "Properties sheet, Property column",
                        PATTERNS.physical_property_id_compliance.pattern,
                    )
                )
            if not PATTERNS.view_id_compliance.match(prop_.concept.suffix):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        prop_.concept,
                        "Concept",
                        "Properties sheet, Concept column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            # Handling Value Type
            if (
                isinstance(prop_.value_type, ConceptEntity)
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
                        isinstance(prop_.value_type, ConceptEntity)
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

        for concept in self._concepts:
            if not PATTERNS.view_id_compliance.match(concept.concept.suffix):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        concept.concept,
                        "Concept",
                        "Concepts sheet, Concept column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            if concept.implements:
                for parent in concept.implements:
                    if not PATTERNS.view_id_compliance.match(parent.suffix):
                        self.issue_list.append(
                            ResourceRegexViolationWarning(
                                parent,
                                "Concept",
                                "Concepts sheet, Implements column",
                                PATTERNS.view_id_compliance.pattern,
                            )
                        )

    def _parent_concepts_by_children(self) -> dict[ConceptEntity, list[ConceptEntity]]:
        parent_concepts_by_children: dict[ConceptEntity, list[ConceptEntity]] = {}
        concepts = self.data_model.model_copy(deep=True).concepts

        for class_ in concepts:
            parent_concepts_by_children[class_.concept] = []
            if class_.implements is None:
                continue
            parent_concepts_by_children[class_.concept].extend(class_.implements)

        return parent_concepts_by_children

    def _namespaces_reassigned(self) -> None:
        prefixes = self.data_model.prefixes.copy()
        prefixes[self.data_model.metadata.namespace.prefix] = (
            self.data_model.metadata.namespace
        )

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
