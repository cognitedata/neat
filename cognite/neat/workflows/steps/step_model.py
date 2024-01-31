import typing
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict

from cognite.neat.app.monitoring.metrics import NeatMetricsCollector
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigs


class Config(BaseModel):
    ...


class Configurable(BaseModel):
    name: str
    value: str | None = None
    label: str | None = None
    type: str | None = None  # string , secret , number , boolean , json , multi_select , single_select
    required: bool = False
    options: list[str] | None = None


class DataContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)


T_Input = TypeVar("T_Input", bound=DataContract)
T_Input1 = TypeVar("T_Input1", bound=DataContract)
T_Input2 = TypeVar("T_Input2", bound=DataContract)
T_Output = TypeVar("T_Output", bound=DataContract)


class Step(ABC):
    description: str = ""
    category: str = "default"
    configurables: ClassVar[list[Configurable]] = []
    scope: str = "core_global"
    metrics: NeatMetricsCollector | None = None
    workflow_configs: WorkflowConfigs | None = None
    version: str = "1.0.0"  # version of the step. All alpha versions considered as experimental
    source: str = (
        "cognite"  # source of the step , can be source identifier or url , for instance github url for instance.
    )
    docs_url: str = "https://cognite-neat.readthedocs-hosted.com/en/latest/"  # url to the documentation of the step

    def __init__(self, data_store_path: Path | None = None):
        self.log: bool = False
        self.configs: dict[str, str] = {}
        self.complex_configs: dict[
            str, typing.Any
        ] = {}  # complex configs are meant for more complex configurations. Value can be any type.
        self.workflow_id: str = ""
        self.workflow_run_id: str = ""
        self.data_store_path = Path(data_store_path) if data_store_path is not None else Path.cwd()

    @property
    def _not_configured_message(self) -> str:
        return f"Step {type(self).__name__} has not been configured."

    def set_metrics(self, metrics: NeatMetricsCollector | None):
        self.metrics = metrics

    def set_workflow_configs(self, configs: WorkflowConfigs | None):
        self.workflow_configs = configs

    def set_workflow_metadata(self, workflow_id: str, workflow_run_id: str):
        self.workflow_id = workflow_id
        self.workflow_run_id = workflow_run_id

    def configure(self, configs: dict[str, str], complex_configs: dict[str, typing.Any] | None = None):
        if complex_configs is None:
            complex_configs = {}
        self.configs = configs
        self.complex_configs = complex_configs

    def set_flow_context(self, context: dict[str, DataContract]):
        self.flow_context = context

    @abstractmethod
    def run(self, *input_data: DataContract) -> DataContract | tuple[FlowMessage, DataContract] | FlowMessage:
        ...
