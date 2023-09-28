import importlib
import inspect
import logging
import os
import sys
import types
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import cognite.neat.workflows.steps.lib
from cognite.neat.app.monitoring.metrics import NeatMetricsCollector
from cognite.neat.exceptions import InvalidWorkFlowError
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigs
from cognite.neat.workflows.steps.step_model import Configurable, DataContract, Step, T_Output


class StepMetadata(BaseModel):
    name: str
    description: str = ""
    category: str = "default"  # defines the category the step belongs to (e.g. "data", "model", "test")
    scope: str = "global"  # defines the scope of the step (e.g. "global", local to a specific workflow)
    input: list[str]
    output: list[str]
    configurables: list[Configurable] = []


class StepsRegistry:
    def __init__(self, data_store_path: Path | None = None):
        self._step_classes: list[Step] = []
        self.user_steps_path = Path(data_store_path) / "steps"
        self.data_store_path = data_store_path

    def load_step_classes(self):
        if self._step_classes:
            # classes already loaded - no need to reload
            return
        for name, step_cls in inspect.getmembers(cognite.neat.workflows.steps.lib):
            if inspect.isclass(step_cls):
                logging.info(f"Loading NEAT step {name}")
                self._step_classes.append(step_cls)
        try:
            if self.user_steps_path:
                self.load_custom_step_classes(self.user_steps_path, scope="global")
        except Exception:
            logging.info(f"No user defined modules provided in {self.user_steps_path}")

    def load_workflow_step_classes(self, workflow_name: str):
        workflow_steps_path = Path(self.data_store_path) / "workflows" / workflow_name
        if workflow_steps_path.exists():
            self.load_custom_step_classes(workflow_steps_path, scope="workflow")

    def load_custom_step_classes(self, custom_steps_path: Path, scope: str = "global"):
        sys.path.append(str(custom_steps_path))
        for step_module_name in os.listdir(custom_steps_path):
            step_module_path = custom_steps_path / Path(step_module_name)
            if step_module_name.startswith("__") or (
                step_module_path.is_file() and not step_module_name.endswith(".py")
            ):
                continue
            full_module_name = step_module_name.replace(".py", "")
            if full_module_name in sys.modules:
                logging.info(f"Reloading existing workflow module {full_module_name}")
                steps_module = importlib.reload(sys.modules[full_module_name])
            else:
                steps_module = importlib.import_module(full_module_name)
                logging.info(f"Loading user defined step from {steps_module}")
            for name, step_cls in inspect.getmembers(steps_module):
                base_class = getattr(step_cls, "__bases__", None)
                if (
                    name.startswith("__")
                    or base_class is None
                    or len(base_class) == 0
                    or base_class[0].__name__ != "Step"
                ):
                    continue
                logging.info(f"Loading user defined step {name} from {steps_module}")
                if inspect.isclass(step_cls):
                    step_cls.scope = scope
                    is_new_class = True
                    for i, step in enumerate(self._step_classes):
                        if step.__name__ == step_cls.__name__:
                            logging.info(f"Reloading user defined step {name} class {step_cls.__name__}")
                            self._step_classes[i] = step_cls
                            is_new_class = False
                    if is_new_class:
                        logging.info(f"Loading NEW user defined step {name} class {step_cls.__name__}")
                        self._step_classes.append(step_cls)

    def run_step(
        self,
        step_name: str,
        flow_context: dict[str, DataContract],
        metrics: NeatMetricsCollector | None = None,
        workflow_configs: WorkflowConfigs | None = None,
        step_configs: dict[str, Any] | None = None,
    ) -> T_Output | None:
        for step_cls in self._step_classes:
            if step_cls.__name__ == step_name:
                step_obj: Step = step_cls(self.data_store_path)
                step_obj.configure(step_configs)
                step_obj.set_flow_context(flow_context)
                step_obj.set_metrics(metrics)
                step_obj.set_workflow_configs(workflow_configs)
                signature = inspect.signature(step_obj.run)
                parameters = signature.parameters
                is_valid = True
                input_data = []
                missing_data = []
                for parameter in parameters.values():
                    try:
                        if parameter.annotation is FlowMessage:
                            input_data.append(flow_context["FlowMessage"])
                        else:
                            if isinstance(parameter.annotation, types.UnionType):
                                for param in parameter.annotation.__args__:
                                    if (
                                        param.__name__ != "_empty"
                                        and param.__name__ in flow_context
                                        and flow_context[param.__name__] is not None
                                    ):
                                        input_data.append(flow_context[param.__name__])
                                        break  # Only one variable can be used as input
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
        for step_cls in self._step_classes:
            try:
                signature = inspect.signature(step_cls.run)
                parameters = signature.parameters
                input_data = []
                output_data = []
                for parameter in parameters.values():
                    if isinstance(parameter.annotation, types.UnionType):
                        for param in parameter.annotation.__args__:
                            if param.__name__ != "_empty":
                                input_data.append(param.__name__)
                    elif parameter.annotation.__name__ != "_empty":
                        input_data.append(parameter.annotation.__name__)
                return_annotation = signature.return_annotation
                if return_annotation:
                    if isinstance(return_annotation, types.UnionType):
                        for annotation in return_annotation.__args__:
                            output_data.append(annotation.__name__)
                    elif isinstance(return_annotation, tuple):
                        for annotation in return_annotation:
                            output_data.append(annotation.__name__)
                    else:
                        output_data.append(return_annotation.__name__)
                steps.append(
                    StepMetadata(
                        name=step_cls.__name__,
                        scope=step_cls.scope,
                        input=input_data,
                        description=step_cls.description,
                        category=step_cls.category,
                        output=output_data,
                        configurables=step_cls.configurables,
                    )
                )
            except AttributeError as e:
                logging.error(f"Step {step_cls.__name__} does not have a run method.Error: {e}")

        return steps
