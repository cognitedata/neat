from abc import ABC
from dataclasses import dataclass

from .base import ValidationWarning


@dataclass(frozen=True)
class OntologyWarning(ValidationWarning, ABC): ...


@dataclass(frozen=True)
class OntologyMultiLabeledPropertyWarning(OntologyWarning):
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
class OntologyMultiDefinitionPropertyWarning(OntologyWarning):
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
class OntologyMultiTypePropertyWarning(OntologyWarning):
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
class OntologyMultiRangePropertyWarning(OntologyWarning):
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
class OntologyMultiDomainPropertyWarning(OntologyWarning):
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
