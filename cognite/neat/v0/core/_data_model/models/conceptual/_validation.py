import itertools
from collections import Counter, defaultdict

from cognite.neat.v0.core._constants import get_base_concepts
from cognite.neat.v0.core._data_model._constants import PATTERNS, EntityTypes
from cognite.neat.v0.core._data_model.models._import_contexts import ImportContext, SpreadsheetContext
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity, UnknownEntity
from cognite.neat.v0.core._data_model.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.errors._resources import (
    ResourceDuplicatedError,
    ResourceNotDefinedError,
)
from cognite.neat.v0.core._issues.warnings._models import (
    ConceptOnlyDataModelWarning,
    ConversionToPhysicalModelImpossibleWarning,
    DanglingPropertyWarning,
    UndefinedConceptWarning,
)
from cognite.neat.v0.core._issues.warnings._resources import (
    ResourceNotDefinedWarning,
    ResourceRegexViolationWarning,
)
from cognite.neat.v0.core._utils.text import humanize_collection

from ._verified import ConceptualDataModel


class ConceptualValidation:
    """This class does all the validation of the conceptual data model that have dependencies
    between components."""

    def __init__(
        self,
        data_model: ConceptualDataModel,
        context: ImportContext | None = None,
    ):
        # import here to avoid circular import issues
        from cognite.neat.v0.core._data_model.analysis._base import DataModelAnalysis

        self.data_model = data_model
        self.analysis = DataModelAnalysis(self.data_model)
        self._read_info_by_spreadsheet = context if isinstance(context, SpreadsheetContext) else SpreadsheetContext({})
        self._metadata = data_model.metadata
        self._properties = data_model.properties
        self._concepts = data_model.concepts
        self._cdf_concepts = {
            ConceptEntity.load(concept_as_string) for concept_as_string in get_base_concepts(base_model="CogniteCore")
        }
        self.issue_list = IssueList()

    def validate(self) -> IssueList:
        self._duplicated_resources()
        self._namespaces_reassigned()
        self._concepts_without_properties_exist()
        self._concepts_with_properties_defined()
        self._ancestors_defined()

        self._object_properties_use_defined_concepts()
        self._dangling_properties()

        self._concept_only_data_model()
        self._regex_compliance_with_physical_data_model()
        self._physical_data_model_conversion()

        return self.issue_list

    def _physical_data_model_conversion(self) -> None:
        """Check if the conceptual data model has issues that will likely lead
        to problems when converting to a physical data model."""
        warning_types_preventing_conversion = [
            ConceptOnlyDataModelWarning,
            ResourceRegexViolationWarning,
            ResourceNotDefinedWarning,
            UndefinedConceptWarning,
            DanglingPropertyWarning,
        ]

        if seen_warnings := frozenset(
            [
                warning_type.__name__
                for warning_type in warning_types_preventing_conversion
                if self.issue_list.has_warning_type(warning_type)
            ]
        ):
            self.issue_list.append_if_not_exist(ConversionToPhysicalModelImpossibleWarning(issue_types=seen_warnings))

    def _concept_only_data_model(self) -> None:
        """Check if the data model only consists of concepts without any properties."""
        if not self._properties:
            self.issue_list.append_if_not_exist(ConceptOnlyDataModelWarning())

    def _dangling_properties(self) -> None:
        """Check if there are properties that do not reference any concept."""
        dangling_properties = [prop for prop in self._properties if prop.concept == UnknownEntity()]
        if dangling_properties:
            for prop in dangling_properties:
                self.issue_list.append_if_not_exist(DanglingPropertyWarning(property_id=prop.property_))

    def _duplicated_resources(self) -> None:
        properties_sheet_info = self._read_info_by_spreadsheet.get("Properties")
        concepts_sheet_info = self._read_info_by_spreadsheet.get("Concepts")

        visited = defaultdict(list)
        for row_no, property_ in enumerate(self._properties):
            visited[property_._identifier()].append(
                properties_sheet_info.adjusted_row_number(row_no) if properties_sheet_info else row_no + 1
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
                concepts_sheet_info.adjusted_row_number(row_no) if concepts_sheet_info else row_no + 1
            )

        for identifier, rows in visited.items():
            if len(rows) == 1:
                continue
            self.issue_list.append_if_not_exist(
                ResourceDuplicatedError(
                    identifier[0],
                    "concept",
                    (
                        f"the Concepts sheet at row {humanize_collection(rows)}"
                        " if data model is read from a spreadsheet."
                    ),
                )
            )

    def _concepts_without_properties_exist(self) -> None:
        """This validation checks if concepts have properties defined or inherit properties from other concepts."""
        concepts = {concept.concept for concept in self._concepts}
        ancestors_by_concept = self.analysis.parents_by_concept(include_ancestors=True, include_different_space=True)
        concepts_with_properties = self.analysis.defined_concepts().union(self._cdf_concepts)

        if candidate_concepts := concepts.difference(concepts_with_properties):
            for concept in candidate_concepts:
                # Here we check if at least one of the ancestors of the concept has properties
                if (ancestors := ancestors_by_concept.get(concept)) and ancestors.intersection(
                    concepts_with_properties
                ):
                    continue

                self.issue_list.append_if_not_exist(UndefinedConceptWarning(concept_id=str(concept)))

    def _concepts_with_properties_defined(self) -> None:
        """This validation checks if concepts to which properties are attached are defined."""
        concepts = {concept.concept for concept in self._concepts}
        concepts_with_properties = {property_.concept for property_ in self._properties} - {UnknownEntity()}

        if undefined_concepts_with_properties := concepts_with_properties.difference(concepts):
            for concept in undefined_concepts_with_properties:
                self.issue_list.append_if_not_exist(
                    ResourceNotDefinedError(
                        identifier=concept,
                        resource_type="concept",
                        location="Concepts sheet",
                    )
                )

    def _ancestors_defined(self) -> None:
        """This is a validation to check if the ancestor concepts (e.g. parents) are defined."""
        concepts = {concept.concept for concept in self._concepts}.union(self._cdf_concepts)
        ancestors = set(
            itertools.chain.from_iterable(
                self.analysis.parents_by_concept(include_ancestors=True, include_different_space=True).values()
            )
        ).difference(self._cdf_concepts)

        if undefined_ancestor := ancestors.difference(concepts):
            for ancestor in undefined_ancestor:
                self.issue_list.append_if_not_exist(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=ancestor,
                        location="Concepts sheet",
                    )
                )

    def _object_properties_use_defined_concepts(self) -> None:
        """Check if the value types of object properties are defined as concepts."""

        concepts = {concept.concept for concept in self._concepts}
        # We remove UnknownEntity from the concepts to avoid false positives
        # as `UnknownEntity` is used as a placeholder when the value type is not defined.
        value_types = {
            property_.value_type
            for property_ in self.data_model.properties
            if property_.type_ == EntityTypes.object_property
        }.difference({UnknownEntity()})

        if undefined_value_types := value_types.difference(concepts):
            for value_type in undefined_value_types:
                self.issue_list.append_if_not_exist(
                    ResourceNotDefinedWarning(
                        resource_type="concept",
                        identifier=value_type,
                        location="Concepts sheet",
                    )
                )

    def _regex_compliance_with_physical_data_model(self) -> None:
        """Check regex compliance with DMS of properties, classes and value types."""

        for prop_ in self._properties:
            if not PATTERNS.physical_property_id_compliance.match(prop_.property_):
                self.issue_list.append_if_not_exist(
                    ResourceRegexViolationWarning(
                        prop_.property_,
                        "Property",
                        "Properties sheet, Property column",
                        PATTERNS.physical_property_id_compliance.pattern,
                    )
                )
            if prop_.concept != UnknownEntity() and not PATTERNS.view_id_compliance.match(prop_.concept.suffix):
                self.issue_list.append_if_not_exist(
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
                self.issue_list.append_if_not_exist(
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
                        self.issue_list.append_if_not_exist(
                            ResourceRegexViolationWarning(
                                value_type,
                                "Value Type",
                                "Properties sheet, Value Type column",
                                PATTERNS.view_id_compliance.pattern,
                            )
                        )

        for concepts in self._concepts:
            if not PATTERNS.view_id_compliance.match(concepts.concept.suffix):
                self.issue_list.append_if_not_exist(
                    ResourceRegexViolationWarning(
                        concepts.concept,
                        "Concept",
                        "Concepts sheet, Concept column",
                        PATTERNS.view_id_compliance.pattern,
                    )
                )

            if concepts.implements:
                for parent in concepts.implements:
                    if not PATTERNS.view_id_compliance.match(parent.suffix):
                        self.issue_list.append_if_not_exist(
                            ResourceRegexViolationWarning(
                                parent,
                                "Concept",
                                "Concepts sheet, Implements column",
                                PATTERNS.view_id_compliance.pattern,
                            )
                        )

    def _namespaces_reassigned(self) -> None:
        prefixes = self.data_model.prefixes.copy()
        prefixes[self.data_model.metadata.namespace.prefix] = self.data_model.metadata.namespace

        if len(set(prefixes.values())) != len(prefixes):
            reused_namespaces = [value for value, count in Counter(prefixes.values()).items() if count > 1]
            impacted_prefixes = [key for key, value in prefixes.items() if value in reused_namespaces]
            self.issue_list.append_if_not_exist(
                NeatValueError(
                    "Namespace collision detected. The following prefixes "
                    f"are assigned to the same namespace: {impacted_prefixes}"
                    f"\nImpacted namespaces: {reused_namespaces}"
                    "\nMake sure that each unique namespace is assigned to a unique prefix"
                )
            )
