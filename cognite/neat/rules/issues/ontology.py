from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from .base import NeatValidationError, ValidationWarning

__all__ = [
    "OntologyError",
    "OntologyWarning",
]


@dataclass(frozen=True)
class OntologyError(NeatValidationError, ABC): ...


@dataclass(frozen=True)
class OntologyWarning(ValidationWarning, ABC): ...


@dataclass(frozen=True)
class OntologyMultiLabeledProperty(OntologyWarning):
    """This warning occurs when a property is given multiple labels, typically if the
    same property is defined for different classes but different name is given

    Args:
        property_id: property id that raised warning due to multiple labels
        names: list of names of property

    Notes:
        This would be automatically fixed by taking the first label (aka name) of the property.
    """

    description = (
        "This warning occurs when a property is given multiple labels,"
        " typically if the same property is defined for different "
        "classes but different name is given."
    )
    fix = "This would be automatically fixed by taking the first label (aka name) of the property."

    property_id: str
    names: list[str] | None = None

    def message(self) -> str:
        message = (
            "Property should have single preferred label (human readable name)."
            f"Currently property '{self.property_id}' has multiple preferred labels: {', '.join(self.names or [])} !"
            f"Only the first name, i.e. '{self.names[0] if self.names else ''}' will be considered!"
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class OntologyMultiDefinitionProperty(OntologyWarning):
    """This warning occurs when a property is given multiple human readable definitions,
    typically if the same property is defined for different classes where each definition
    is different.

    Args:
        property_id: property id that raised warning due to multiple definitions

    Notes:
        This would be automatically fixed by concatenating all definitions.
    """

    description = (
        "This warning occurs when a property is given multiple human readable definitions,"
        " typically if the same property is defined for different "
        "classes where each definition is different."
    )
    fix = "This would be automatically fixed by concatenating all definitions."

    property_id: str

    def message(self):
        message = (
            f"Multiple definitions (aka comments) of property '{self.property_id}' detected."
            " Definitions will be concatenated."
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class OntologyMultiTypeProperty(OntologyWarning):
    """This warning occurs when a same property is define for two object/classes where
    its expected value type is different in one definition, e.g. acts as an edge, while in
    other definition acts as and attribute

    Args:
        property_id: property id that raised warning due to multi type definition
        types: list of types of property

    Notes:
        If a property takes different value types for different objects, simply define
        new property. It is bad practice to have multi type property!
    """

    description = (
        "This warning occurs when a same property is define for two object/classes where"
        " its expected value type is different in one definition, e.g. acts as an edge, while in "
        "other definition acts as and attribute"
    )
    fix = "If a property takes different value types for different objects, simply define new property"

    property_id: str
    types: list[str] | None = None

    def message(self) -> str:
        message = (
            "It is bad practice to have multi type property! "
            f"Currently property '{self.property_id}' is defined as multi type property: {', '.join(self.types or [])}"
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class OntologyMultiRangeProperty(OntologyWarning):
    """This warning occurs when a property takes range of values which consists of union
    of multiple value types

    Args:
        property_id: property id that raised warning due to multi range definition
        range_of_values: list of ranges that property takes

    Notes:
        If a property takes different range of values, simply define new property.
    """

    description = (
        "This warning occurs when a property takes range of values which consists of union of multiple value types."
    )
    fix = "If a property takes different range of values, simply define new property"
    property_id: str
    range_of_values: list[str] | None = None

    def message(self) -> str:
        message = (
            "It is bad practice to have property that take various range of values! "
            f"Currently property '{self.property_id}' has multiple ranges: {', '.join(self.range_of_values or [])}"
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class OntologyMultiDomainProperty(OntologyWarning):
    """This warning occurs when a property is reused for more than one classes

    Args:
        property_id: property id that raised warning due to reuse definition
        classes: list of classes that use the same property
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        No need to fix this, but make sure that property type is consistent across different
        classes and that ideally takes the same range of values
    """

    description = "This warning occurs when a property is reused for more than one classes."
    fix = (
        "No need to fix this, but make sure that property type is consistent"
        " across different classes and that ideally takes the same range of values"
    )
    property_id: str
    classes: list[str] | None = None

    def message(self) -> str:
        message = (
            f"Currently property '{self.property_id}' is defined for multiple classes: {', '.join(self.classes or [])}"
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class PropertiesDefinedMultipleTimes(OntologyError):
    """This error is raised during export of Transformation Rules to DMS schema when
    when properties are defined multiple times for the same class.

    Args:
        report: report on properties which are defined multiple times
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure to check validation report of Transformation Rules and fix DMS related warnings.
    """

    description = (
        "This error is raised during export of Transformation Rules to "
        "DMS schema when properties are defined multiple times for the same class."
    )
    fix = "Make sure to check validation report of Transformation Rules and fix DMS related warnings."

    report: str

    def message(self) -> str:
        message = f"Following properties defined multiple times for the same class(es): {self.report}"

        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class PropertyDefinitionsNotForSameProperty(OntologyError):
    """This error is raised if property definitions are not for linked to the same
    property id when exporting rules to ontological representation.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    description = "This error is raised if property definitions are not for linked to the same property id"

    def message(self):
        message = "All definitions should have the same property_id! Aborting."

        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class PrefixMissing(OntologyError):
    """Prefix, which is in the 'Metadata' sheet, is missing.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    description = "Prefix is missing from the 'Metadata' sheet."
    example = "There is no prefix in the 'Metadata' sheet."
    fix = "Specify the prefix if prefix in the 'Metadata' sheet."

    def message(self) -> str:
        message = "Missing prefix stored in 'Metadata' sheet."
        message += f"\nDescription: {self.description}"
        message += f"\nExample: {self.example}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class MissingDataModelPrefixOrNamespace(ValidationWarning):
    """Prefix and/or namespace are missing in the 'Metadata' sheet

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
    Add missing prefix and/or namespace in the 'Metadata' sheet
    """

    description = "Either prefix or namespace or both are missing in the 'Metadata' sheet"
    fix = "Add missing prefix and/or namespace in the 'Metadata' sheet"

    def message(self) -> str:
        message = (
            "Instances sheet is present but prefix and/or namespace are missing in 'Metadata' sheet."
            "Instances sheet will not be processed!"
        )
        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class MetadataSheetNamespaceNotDefined(OntologyError):
    """namespace, which is in the 'Metadata' sheet, is not defined

    Args:
        namespace: namespace that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if `namespace` in the `Metadata` sheet is properly constructed as valid URL
        containing only allowed characters.

    """

    description = "namespace, which is in the 'Metadata' sheet, is missing"
    example: ClassVar[str] = "Example of a valid namespace 'http://www.w3.org/ns/sparql#'"
    fix = "Define the 'namespace' in the 'Metadata' sheet."

    def message(self) -> str:
        message = "Missing namespace  in 'Metadata' sheet."
        message += f"\nDescription: {self.description}"
        message += f"\nExample: {self.example}"
        message += f"\nFix: {self.fix}"
        return message
