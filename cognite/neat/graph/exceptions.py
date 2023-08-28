"""This module contains the definition of validation errors and warnings raised during graph methods
"""

from cognite.neat.exceptions import NeatException


class UnsupportedPropertyType(NeatException):
    type_: str = "UnsupportedPropertyType"
    code: int = 1000
    description: str = "Unsupported property type when processing the graph capturing sheet."
    example: str = ""
    fix: str = ""

    def __init__(self, property_type: str, verbose=False):
        self.property_type = property_type

        self.message = (
            f"Property type {self.property_type} is not supported. "
            " Only the following property types are supported: DatatypeProperty and ObjectProperty"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)
