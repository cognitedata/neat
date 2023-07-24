class NeatException(Exception):
    """Base class for all exceptions raised by NEAT."""

    ...


class NeatImportError(NeatException):
    """Cognite Import Error

    Raised if the user attempts to use functionality which requires an uninstalled package.

    Args:
        module (str): Name of the module which could not be imported
        extra (str): The name of the extra you use to install it with neat.
    """

    def __init__(self, module: str, extra: str):
        self.module = module
        self.message = (
            f"This functionality requires {self.module}. "
            f'You can include it in your neat installation with `pip install "cognite-neat[{extra}]"`.'
        )

    def __str__(self) -> str:
        return self.message


class InvalidWorkFlowError(NeatException):
    """InvalidWorkFlowError
    Raised if an invalid workflow is provided to the Workflow Manager.
    Args:
        step_name (str): Name of the step which could not be run
        missing_data (list[str]): The missing data for the step.
    """

    def __init__(self, step_name, missing_data: list[str]):
        self.message = f"In the workflow step {step_name} the following data is missing: {missing_data}."

    def __str__(self) -> str:
        return self.message
