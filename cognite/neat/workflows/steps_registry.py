import importlib
import inspect
from pathlib import Path
from typing import Type

from pydantic import BaseModel
from cognite.neat.exceptions import InvalidWorkFlowError
from cognite.neat.workflows.model import WorkflowConfigItem
import cognite.neat.workflows.steps.lib
import logging

from cognite.neat.workflows.steps.step_model import DataContract, T_Output
from cognite.neat.workflows.steps.step_model import Step


class StepMetadata(BaseModel):
    name: str
    description: str = ""
    input: list[str]
    output: list[str]
    configuration_templates: list[WorkflowConfigItem] = []


class StepsRegistry:
    def __init__(self, metrics=None, data_store_path: str | None = None):
        self._step_classes: list[Step] = []
        self.user_steps_path = Path(data_store_path) / "steps"
        self.metrics = metrics
        self.data_store_path = data_store_path

    def load_step_classes(self):
        if self._step_classes:
            # classes already loaded - no need to reload
            return
        for name, step_cls in inspect.getmembers(cognite.neat.workflows.steps.lib):
            if inspect.isclass(step_cls):
                self._step_classes.append([name, step_cls])
        try:
            if self.user_steps_path:
                steps_module = importlib.import_module(self.user_steps_path)
                for name, step_cls in inspect.getmembers(steps_module):
                    if inspect.isclass(step_cls):
                        self._step_classes.append([name, step_cls])
        except Exception as e:
            logging.warn(f"No user defined modules provided in {self.user_steps_path} : {e}")

    def run_step(self, step_name: str, flow_context: dict[str, Type[DataContract]]) -> T_Output | None:
        for name, step_cls in self._step_classes:
            if name == step_name:
                step_obj = step_cls(self.metrics, self.data_store_path)
                step_obj.set_flow_context(flow_context)
                signature = inspect.signature(step_obj.run)
                parameters = signature.parameters
                is_valid = True
                input_data = []
                missing_data = []
                for parameter in parameters.values():
                    try:
                        if parameter.annotation.__name__ == "FlowMessage":
                            input_data.append(flow_context["FlowMessage"])
                        else:
                            input_data.append(flow_context[parameter.annotation.__name__])
                    except KeyError:
                        is_valid = False
                        logging.error(f"Missing data for step {step_name} parameter {parameter.name}")
                        missing_data.append(parameter.annotation.__name__)
                        continue
                if not is_valid:
                    raise InvalidWorkFlowError(step_name, missing_data)
                return step_obj.run(*input_data)
    
    def get_list_of_steps(self):
        steps: list[StepMetadata] = []
        for name, step_cls in self._step_classes:
            signature = inspect.signature(step_cls.run)
            parameters = signature.parameters
            input_data = []
            output_data = []
            for parameter in parameters.values():
                if parameter.annotation.__name__ != "_empty":
                    input_data.append(parameter.annotation.__name__)
            return_annotation = signature.return_annotation
            if return_annotation:
                if return_annotation.__name__ == "Tuple":
                    for annotation in return_annotation.__args__:
                        output_data.append(annotation.__name__)
                else:
                    output_data.append(return_annotation.__name__)
            # logging.info(f"Step {name} output data: {return_annotation}")
            steps.append(
                StepMetadata(
                    name=name,
                    input=input_data,
                    description=step_cls.description,
                    output=output_data,
                    configuration_templates=step_cls.configuration_templates,
                )
            )

        return steps
