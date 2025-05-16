import itertools
from collections import Counter, defaultdict
from collections.abc import Iterable

from cognite.neat.core._data_model._constants import PATTERNS, EntityTypes
from cognite.neat.core._data_model.models.entities import ConceptEntity, UnknownEntity
from cognite.neat.core._data_model.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat.core._issues import IssueList
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._issues.errors._resources import (
    ResourceDuplicatedError,
    ResourceNotDefinedError,
)
from cognite.neat.core._issues.warnings._models import UndefinedConceptWarning
from cognite.neat.core._issues.warnings._resources import (
    ResourceNotDefinedWarning,
    ResourceRegexViolationWarning,
)
from cognite.neat.core._utils.spreadsheet import SpreadsheetRead
from cognite.neat.core._utils.text import humanize_collection

from ._verified import ConceptualDataModel, ConceptualProperty


class ConceptualValidation:
    """This class does all the validation of the conceptual data model that have dependencies
    between components."""

    def __init__(
        self,
        data_model: ConceptualDataModel,
        read_info_by_spreadsheet: dict[str, SpreadsheetRead] | None = None,
    ):
        self.data_model = data_model
        self._read_info_by_spreadsheet = read_info_by_spreadsheet or {}
        self._metadata = data_model.metadata
        self._properties = data_model.properties
        self._concepts = data_model.concepts
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._duplicated_resources()
        self._namespaces_reassigned()
        self._classes_without_properties()
        self._undefined_classes()
        self._parent_concept_defined()
        self._referenced_classes_exist()
        self._referenced_value_types_exist()
        self._regex_compliance_with_dms()

        return self.issue_list

    def _duplicated_resources(self) -> None:
        properties_sheet = self._read_info_by_spreadsheet.get("Properties")
        concepts_sheet = self._read_info_by_spreadsheet.get("Concepts")

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
        for row_no, concept in enumerate(self._concepts):
            visited[concept._identifier()].append(
                concepts_sheet.adjusted_row_number(row_no) if concepts_sheet else row_no + 1
            )

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            self.issue_list.append(
                ResourceDuplicatedError(
                    identifier[0],
                    "concept",
                    (f"the Classes sheet at row {humanize_collection(rows)} if data model is read from a spreadsheet."),
                )
            )

    def _classes_without_properties(self) -> None:
        defined_concepts = {concept.concept for concept in self._concepts}
        referred_classes = {property_.concept for property_ in self._properties}
        concept_parent_pairs = self._concept_parent_pairs()

        if concepts_without_properties := defined_concepts.difference(referred_classes):
            for concept in concepts_without_properties:
                # USE CASE: class has no direct properties and no parents with properties
                # and it is a class in the prefix of data model, as long as it is in the
                # same prefix, meaning same space
                if not concept_parent_pairs[concept] and concept.prefix == self._metadata.prefix:
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="concept",
                            identifier=concept,
                            location="Properties sheet",
                        )
                    )

    def _undefined_classes(self) -> None:
        defined_concept = {concept.concept for concept in self._concepts}
        referred_concepts = {property_.concept for property_ in self._properties}

        if undefined_concepts := referred_concepts.difference(defined_concept):
            for concept in undefined_concepts:
                self.issue_list.append(
                    ResourceNotDefinedError(
                        identifier=concept,
                        resource_type="concept",
                        location="Concepts sheet",
                    )
                )

    def _parent_concept_defined(self) -> None:
        """This is a validation to check if the parent concept is defined."""
        concept_parent_pairs = self._concept_parent_pairs()
        concepts = set(concept_parent_pairs.keys())
        parents = set(itertools.chain.from_iterable(concept_parent_pairs.values()))

        if undefined_parents := parents.difference(concepts):
            for parent in undefined_parents:
                if parent.prefix != self._metadata.prefix:
                    self.issue_list.append(UndefinedConceptWarning(concept_id=str(parent)))
                else:
                    self.issue_list.append(
                        ResourceNotDefinedWarning(
                            resource_type="concept",
                            identifier=parent,
                            location="Concepts sheet",
                        )
                    )

    def _referenced_classes_exist(self) -> None:
        # needs to be complete for this validation to pass
        defined_concept = {concept.concept for concept in self._concepts}
        classes_with_explicit_properties = {property_.concept for property_ in self._properties}

        # USE CASE: models are complete
        if missing_classes := classes_with_explicit_properties.difference(defined_concept):
            for concept in missing_classes:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=concept,
                        location="Concepts sheet",
                    )
                )

    def _referenced_value_types_exist(self) -> None:
        # adding UnknownEntity to the set of defined classes to handle the case where a property references an unknown
        defined_classes = {concept.concept for concept in self._concepts} | {UnknownEntity()}
        referred_object_types = {
            property_.value_type
            for property_ in self.data_model.properties
            if property_.type_ == EntityTypes.object_property
        }

        if missing_value_types := referred_object_types.difference(defined_classes):
            # Todo: include row and column number
            for missing in missing_value_types:
                self.issue_list.append(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=missing,
                        location="Concepts sheet",
                    )
                )

    def _regex_compliance_with_dms(self) -> None:
        """Check regex compliance with DMS of properties, classes and value types."""

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

        for concepts in self._concepts:
            if not PATTERNS.view_id_compliance.match(concepts.concept.suffix):
                self.issue_list.append(
                    ResourceRegexViolationWarning(
                        concepts.concept,
                        "Concept",
                        "Concepts sheet, Class column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            if concepts.implements:
                for parent in concepts.implements:
                    if not PATTERNS.view_id_compliance.match(parent.suffix):
                        self.issue_list.append(
                            ResourceRegexViolationWarning(
                                parent,
                                "Concept",
                                "Concepts sheet, Implements column",
                                PATTERNS.view_id_compliance.pattern,
                            )
                        )

    def _concept_parent_pairs(self) -> dict[ConceptEntity, list[ConceptEntity]]:
        concept_parent_pairs: dict[ConceptEntity, list[ConceptEntity]] = {}
        concepts = self.data_model.model_copy(deep=True).concepts

        for concept in concepts:
            concept_parent_pairs[concept.concept] = []
            if concept.implements is None:
                continue
            concept_parent_pairs[concept.concept].extend(concept.implements)

        return concept_parent_pairs

    def _namespaces_reassigned(self) -> None:
        prefixes = self.data_model.prefixes.copy()
        prefixes[self.data_model.metadata.namespace.prefix] = self.data_model.metadata.namespace

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


def duplicated_properties(
    properties: Iterable[ConceptualProperty],
) -> dict[tuple[ConceptEntity, str], list[tuple[int, ConceptualProperty]]]:
    concept_properties_by_id: dict[tuple[ConceptEntity, str], list[tuple[int, ConceptualProperty]]] = defaultdict(list)
    for prop_no, prop in enumerate(properties):
        concept_properties_by_id[(prop.concept, prop.property_)].append((prop_no, prop))
    return {k: v for k, v in concept_properties_by_id.items() if len(v) > 1}
