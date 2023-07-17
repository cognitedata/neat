"""This module contains the definition of validation errors and warnings raised by various extractors
"""


from pydantic_core import ErrorDetails, PydanticCustomError


class NeatError(Exception):
    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str

    def to_pydantic_custom_error(self):
        return PydanticCustomError(
            self.type_,
            self.message,
            dict(type_=self.type_, code=self.code, description=self.description, example=self.example, fix=self.fix),
        )

    def to_error_dict(self) -> ErrorDetails:
        return {
            "type": self.type_,
            "loc": (),
            "msg": self.message,
            "input": None,
            "ctx": dict(
                type_=self.type_,
                code=self.code,
                description=self.description,
                example=self.example,
                fix=self.fix,
            ),
        }


class NeatWarning(UserWarning):
    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str


class Warning1(NeatWarning):
    type_: str = "OWLGeneratedTransformationRulesHasErrors"
    code: int = 1
    description: str = (
        "This warning occurs when generating transformation rules from OWL ontology are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, verbose=False):
        self.message = (
            "Transformation rules generated from OWL ontology are invalid!"
            " Consult report.txt for details on the errors and fix them before using the rules file."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class Warning2(NeatWarning):
    type_: str = "OWLGeneratedTransformationRulesHasWarnings"
    code: int = 2
    description: str = (
        "This warning occurs when generating transformation rules from OWL ontology are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, verbose=False):
        self.message = (
            "Transformation rules generated from OWL ontology raised warnings!"
            " Consult report.txt for details on warnings, and fix them prior using the rules file."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page
