import sys
from typing import Any

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

from pydantic import BaseModel, Field, field_validator


class WorkflowState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    RUNNING_WAITING = "RUNNING_WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class StepExecutionStatus(StrEnum):
    SUCCESS = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    STARTED = "STARTED"
    UNKNOWN = "UNKNOWN"
    ABORT_AND_FAIL = "ABORT_AND_FAIL"


class InstanceStartMethod(StrEnum):
    PERSISTENT_INSTANCE_NON_BLOCKING = "persistent_non_blocking"
    PERSISTENT_INSTANCE_BLOCKING = "persistent_blocking"
    EPHEMERAL_INSTANCE = "ephemeral_instance"


class WorkflowStartException(Exception):
    pass


class FlowMessage(BaseModel):
    """A message that can be sent between steps in a workflow.It's the only parameter step takes as input."""

    payload: Any = None  # The payload of the message
    headers: dict[str, str] | None = None  # The headers of the message
    output_text: str | None = None  # The output text of the step that is captured in the execution log
    error_text: str | None = None  # The error text of the step that is captured in the execution log
    next_step_ids: list[
        str
    ] | None = None  # If set, the workflow will skip default route and go to the next step in the list
    step_execution_status: StepExecutionStatus = StepExecutionStatus.UNKNOWN  # The status of the step execution


class StepType(StrEnum):
    PYSTEP = "pystep"
    STD_STEP = "stdstep"
    START_WORKFLOW_TASK_STEP = "start_workflow_task_step"  # Call a workflow from another workflow
    CONTAINER_TASK_STEP = "container_step"  # TODO: implement
    CLI_TASK_STEP = "cli_step"  # TODO: implement
    HTTP_TRIGGER = "http_trigger"
    TIME_TRIGGER = "time_trigger"
    WAIT_FOR_EVENT = "wait_for_event"  # TODO: implement
    EVENT_TRIGGER = "event_trigger"  # TODO: implement


class UIConfig(BaseModel):
    pos_x: int = 0
    pos_y: int = 0


class WorkflowConfigItem(BaseModel):
    name: str
    value: str | None = None
    label: str | None = None
    type: str | None = None
    required: bool = False
    options: list[str] | None = None
    group: str | None = None


class WorkflowStepDefinition(BaseModel):
    id: str
    label: str | None = None
    stype: str = StepType.PYSTEP
    description: str | None = None
    method: str | None = None
    enabled: bool = True
    system_component_id: str | None = None
    trigger: bool = False
    transition_to: list[str] | None = None
    ui_config: UIConfig = UIConfig()
    params: dict[str, str] = Field(default_factory=dict)  # System parameters
    configs: dict[str, Any] = Field(default_factory=dict)  # Step configurations
    complex_configs: dict[str, Any] = Field(default_factory=dict)  # Complex step configurations
    max_retries: int = 0
    retry_delay: int = 3

    @field_validator("configs", "params", mode="before")
    def none_as_empty_dict(cls, value):
        if value is None:
            return {}
        return value


class WorkflowSystemComponent(BaseModel):
    # Container for steps
    id: str
    label: str
    transition_to: list[str] | None = None
    description: str | None = None
    ui_config: UIConfig = UIConfig()


class WorkflowDefinition(BaseModel):
    """Workflow definition"""

    name: str
    description: str | None = None
    implementation_module: str | None = None
    steps: list[WorkflowStepDefinition] = Field(default_factory=list)
    system_components: list[WorkflowSystemComponent] = Field(default_factory=list)
    configs: list[WorkflowConfigItem] = Field(default_factory=list)

    def get_config_item(self, name: str) -> WorkflowConfigItem | None:
        for config in self.configs:
            if config.name == name:
                return config
        return None

    def upsert_config_item(self, config_item: WorkflowConfigItem) -> None:
        for config in self.configs:
            if config.name == config_item.name:
                config.value = config_item.value
                config.label = config_item.label
                config.type = config_item.type
                config.required = config_item.required
                config.options = config_item.options
                config.group = config_item.group
                return
        self.configs.append(config_item)


class WorkflowStepEvent(BaseModel):
    """Workflow step event represent a single step execution"""

    id: str
    system_component_id: str | None = None
    state: StepExecutionStatus
    elapsed_time: float
    timestamp: str
    error: str | None = None
    output_text: str | None = None
    data: Any = None


class WorkflowFullStateReport(BaseModel):
    """Workflow state report is complete log of workflow execution"""

    workflow_name: str | None = None
    workflow_version: str | None = None
    run_id: str | None = None
    state: WorkflowState
    start_time: int | None = None
    end_time: int | None = None
    elapsed_time: float = 0
    last_error: str | None = None
    execution_log: list[WorkflowStepEvent]
    last_updated_time: int | None = None

    @field_validator("start_time", "end_time", mode="before")
    def float_to_int(cls, value):
        if isinstance(value, float):
            return int(value)
        return value


class WorkflowConfigs(BaseModel):
    """Workflow configs"""

    configs: list[WorkflowConfigItem] = []

    def get_config_item(self, config_name: str) -> WorkflowConfigItem | None:
        return next((item for item in self.configs if item.name == config_name), None)

    def set_config_item(self, config_item: WorkflowConfigItem):
        for item in self.configs:
            if item.name == config_item.name:
                item.value = config_item.value
                return
        self.configs.append(config_item)

    def get_config_group_values_by_name(
        self, group_name: str, remove_group_prefix: bool = True
    ) -> dict[str, str | None]:
        return {
            (item.name.removeprefix(item.group) if remove_group_prefix else item.name): item.value
            for item in self.configs
            if item.group == group_name
        }

    def get_config_item_value(self, config_name: str, default_value=None) -> str | None:
        return config.value if (config := self.get_config_item(config_name)) else default_value
