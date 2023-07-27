from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar
from cognite.client import CogniteClient
from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    ...


class DataContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)


T_Input = TypeVar("T_Input", bound=DataContract)

T_Output = TypeVar("T_Output", bound=DataContract)


class Step(ABC):
    def __init__(self, metrics):
        self.log: bool = False
        self.data_store_path: str | None = None
        self.rules_storage_path: str | None = None

        # Comment: Metrics should be optional
        self.metrics = metrics

        # Comment: CDF client is mandatory only for limited number of steps
        # this should be removed and only added to the steps that need it !
        self.cdf_client: CogniteClient | None = None

    def set_global_configs(self, cdf_client: CogniteClient, data_store_path: str, rules_storage_path: str):
        # Comment: This should be removed and only added to the steps that need it !
        # or made optional here
        self.cdf_client = cdf_client

        # Comment data store is bad name, it should be graph store as we are storing graphs
        self.data_store_path = data_store_path
        self.rules_storage_path = rules_storage_path

    @abstractmethod
    def run(self, *input_data: T_Input) -> T_Output:
        ...
