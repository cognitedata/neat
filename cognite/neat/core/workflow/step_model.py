from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar
from cognite.client import CogniteClient
from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    ...


class Data(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)


T_Input = TypeVar("T_Input", bound=Data)

T_Output = TypeVar("T_Output", bound=Data)


class Step(ABC):
    def __init__(self, metrics):
        self.log: bool = False
        self.metrics = metrics
    
    def set_global_configs(self, cdf_client: CogniteClient, data_store_path: str, rules_storage_path: str):
        self.cdf_client = cdf_client
        self.data_store_path = data_store_path
        self.rules_storage_path = rules_storage_path

    @abstractmethod
    def run(self, *input_data: T_Input) -> T_Output:
        ...
