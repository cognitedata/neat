class NeatException(Exception):
    """Base class for all exceptions raised by NEAT."""

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
