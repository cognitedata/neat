from abc import ABC, abstractmethod
from typing import ClassVar, Type, TypeVar
from pydantic import BaseModel, ConfigDict

from cognite.neat.workflows.model import WorkflowConfigItem


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
    
    def __init__(self, metrics, data_store_path: str | None = None, context: dict[str, str] = None):
        self.log: bool = False
        self.data_store_path: str = data_store_path
        # Comment: Metrics should be optional
        self.metrics = metrics or None
    
    def set_flow_context(self, context: dict[str, Type[DataContract]]):
        self.flow_context = context

    @abstractmethod
    def run(self, *input_data: T_Input) -> T_Output:
        ...
