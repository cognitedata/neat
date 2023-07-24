from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class WorkflowState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    RUNNING_WAITING = "RUNNING_WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class StepExecutionStatus(StrEnum):
    SUCCESS = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    STARTED = "STARTED"
    UNKNOWN = "UNKNOWN"


class InstanceStartMethod(StrEnum):
    PERSISTENT_INSTANCE_NON_BLOCKING = "persistent_non_blocking"
    PERSISTENT_INSTANCE_BLOCKING = "persistent_blocking"
    EPHEMERAL_INSTANCE = "ephemeral_instance"


class WorkflowStartException(Exception):
    pass


class FlowMessage(BaseModel):
    """A message that can be sent between steps in a workflow.It's the only parameter step takes as input."""

    payload: Any = None  # The payload of the message
    headers: Optional[dict[str, str]] = None  # The headers of the message
    output_text: Optional[str] = None  # The output text of the step that is captured in the execution log
    error_text: Optional[str] = None  # The error text of the step that is captured in the execution log
    next_step_ids: Optional[
        list[str]
    ] = None  # If set, the workflow will skip default route and go to the next step in the list
    step_execution_status: StepExecutionStatus = StepExecutionStatus.UNKNOWN  # The status of the step execution


class StepType(StrEnum):
    PYSTEP = "pystep"
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
    value: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    required: bool = False
    options: Optional[list[str]] = None
    group: Optional[str] = None


class WorkflowStepDefinition(BaseModel):
    id: str
    label: Optional[str] = None
    stype: str = StepType.PYSTEP
    description: Optional[str] = None
    method: Optional[str] = None
    enabled: bool = True
    system_component_id: Optional[str] = None
    trigger: bool = False
    transition_to: Optional[list[str]] = None
    ui_config: UIConfig = UIConfig()
    params: Optional[dict[str, str]] = None
    max_retries: int = 0
    retry_delay: int = 3


class WorkflowSystemComponent(BaseModel):
    # Container for steps
    id: str
    label: str
    transition_to: Optional[list[str]] = None
    description: Optional[str] = None
    ui_config: UIConfig = UIConfig()


class WorkflowDefinition(BaseModel):
    """Workflow definition"""

    name: str
    description: Optional[str] = None
    implementation_module: Optional[str] = None
    steps: list[WorkflowStepDefinition]
    system_components: Optional[list[WorkflowSystemComponent]] = None
    configs: Optional[list[WorkflowConfigItem]] = None

    def get_config_item(self, name: str) -> WorkflowConfigItem:
        for config in self.configs:
            if config.name == name:
                return config
        return None

    def upsert_config_item(self, config_item: WorkflowConfigItem):
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
    system_component_id: Optional[str] = None
    state: StepExecutionStatus
    elapsed_time: float
    timestamp: str
    error: Optional[str] = None
    output_text: Optional[str] = None
    data: Any = None


class WorkflowFullStateReport(BaseModel):
    """Workflow state report is complete log of workflow execution"""

    workflow_name: Optional[str] = None
    workflow_version: Optional[str] = None
    run_id: Optional[str] = None
    state: WorkflowState
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    elapsed_time: float = 0
    last_error: Optional[str] = None
    execution_log: list[WorkflowStepEvent]

    @field_validator("start_time", "end_time", mode="before")
    def float_to_int(cls, value):
        if isinstance(value, float):
            return int(value)
        return value
