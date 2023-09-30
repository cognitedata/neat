from typing import Any
from warnings import WarningMessage

from pydantic_core import ErrorDetails, PydanticCustomError


class NeatException(Exception):
    """Base class for all exceptions raised by NEAT."""

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
                type_=self.type_, code=self.code, description=self.description, example=self.example, fix=self.fix
            ),
        }


class NeatWarning(UserWarning):
    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str


class NeatImportError(NeatException):
    """Cognite Import Error

    Raised if the user attempts to use functionality which requires an uninstalled package.

    Args:
        module (str): Name of the module which could not be imported
        extra (str): The name of the extra you use to install it with neat.
    """

    type_: str = "NeatImportError"
    code: int = 0
    description: str = "Raised if the user attempts to use functionality which requires an uninstalled package."
    example: str = ""
    fix: str = ""

    def __init__(self, module: str, extra: str, verbose=False):
        self.module = module
        self.message = (
            f"This functionality requires {self.module}. "
            f'You can include it in your neat installation with `pip install "cognite-neat[{extra}]"`.'
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class InvalidWorkFlowError(NeatException):
    """InvalidWorkFlowError
    Raised if an invalid workflow is provided to the Workflow Manager.
    Args:
        step_name (str): Name of the step which could not be run
        missing_data (list[str]): The missing data for the step.
    """

    type_: str = "InvalidWorkFlowError"
    code: int = 1
    description: str = "Raised if an invalid workflow is provided to the Workflow Manager."
    example: str = ""
    fix: str = ""

    def __init__(self, step_name, missing_data: list[str], verbose=False):
        self.message = f"In the workflow step {step_name} the following data is missing: {missing_data}."

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


def wrangle_warnings(list_of_warnings: list[WarningMessage]) -> list[dict]:
    warning_list: list[dict] = []
    for warning in list_of_warnings:
        if issubclass(warning.message.__class__, NeatWarning):
            warning_list.append(_neat_warning_to_dict(warning))
        elif issubclass(warning.message.__class__, Warning):
            warning_list.append(_python_warning_to_dict(warning))
    return warning_list


def _neat_warning_to_dict(warning: WarningMessage) -> dict:
    category: Any = warning.category
    return {
        "type": category.type_,
        "loc": (),
        "msg": str(warning.message),
        "input": None,
        "ctx": dict(
            type_=category.type_,
            code=category.code,
            description=category.description,
            example=category.example,
            fix=category.fix,
        ),
    }


def _python_warning_to_dict(warning: WarningMessage) -> dict:
    return {
        "type": warning.category,
        "loc": (),
        "msg": str(warning.message),
        "input": None,
        "ctx": dict(type_=warning.category, code=None, description=None, example=None, fix=None),
    }
