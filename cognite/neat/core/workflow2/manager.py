import inspect
from typing import Type

from ..exceptions import InvalidWorkFlowError
from .base import Data, Step


class Manager:
    def __init__(self):
        self.data: dict[str, Type[Data]] = {}

    def run_workflow(self, workflow: list[Type[Step]]):
        for step in workflow:
            signature = inspect.signature(step.run)
            parameters = signature.parameters

            is_valid = True
            input_data = []
            missing_data = []
            for parameter in parameters.values():
                try:
                    input_data.append(self.data[parameter.annotation.__name__])
                except KeyError:
                    is_valid = False
                    missing_data.append(parameter.annotation.__name__)
                    continue
            if not is_valid:
                raise InvalidWorkFlowError(type(step).__name__, missing_data)

            output = step.run(*input_data)
            if output is not None:
                self.data[signature.return_annotation.__name__] = output
