from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar
from pydantic import BaseModel, ConfigDict
from cognite.neat.app.monitoring.metrics import NeatMetricsCollector

from cognite.neat.workflows.model import WorkflowConfigItem, WorkflowConfigs


class Config(BaseModel):
    ...


class DataContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)


T_Input = TypeVar("T_Input", bound=DataContract)

T_Output = TypeVar("T_Output", bound=DataContract)


class Step(ABC):
    description: str = ""
    category: str = "default"
    configuration_templates: list[WorkflowConfigItem] = []
    scope: str = "global"
    metrics: NeatMetricsCollector | None = None
    configs: WorkflowConfigs | None = None

    def __init__(self, data_store_path: str | None = None):
        self.log: bool = False
        self.data_store_path: str = data_store_path

    def set_metrics(self, metrics: NeatMetricsCollector):
        self.metrics = metrics

    def set_workflow_configs(self, configs: WorkflowConfigs):
        self.configs = configs

    def set_flow_context(self, context: dict[str, DataContract]):
        self.flow_context = context

    @abstractmethod
    def run(self, *input_data: T_Input) -> T_Output:
        ...
