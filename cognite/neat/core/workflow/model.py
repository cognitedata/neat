import typing
from enum import StrEnum

from pydantic import BaseModel


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


class FlowMessage(BaseModel):
    """A message that can be sent between steps in a workflow.It's the only parameter step takes as input."""

    payload: typing.Any = None  # The payload of the message
    headers: dict[str, str] = None  # The headers of the message
    output_text: str = None  # The output text of the step that is captured in the execution log
    error_text: str = None  # The error text of the step that is captured in the execution log
    next_step_ids: list[str] = None  # If set, the workflow will skip default route and go to the next step in the list
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
    value: str = None
    label: str = None
    type: str = None
    required: bool = False
    options: list[str] = None
    group: str = None


class WorkflowStepDefinition(BaseModel):
    id: str
    label: str = None
    stype: str = StepType.PYSTEP
    description: str = None
    method: str = None
    enabled: bool = True
    system_component_id: str = None
    trigger: bool = False
    transition_to: list[str] = None
    ui_config: UIConfig = UIConfig()
    params: dict[str, str] = None
    max_retries: int = 0
    retry_delay: int = 3


class WorkflowSystemComponent(BaseModel):
    # Container for steps
    id: str
    label: str
    transition_to: list[str] = None
    description: str = None
    ui_config: UIConfig = UIConfig()


class WorkflowDefinition(BaseModel):
    """Workflow definition"""

    name: str
    description: str = None
    implementation_module: str = None
    steps: list[WorkflowStepDefinition]
    system_components: list[WorkflowSystemComponent] = None
    configs: list[WorkflowConfigItem] = None

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
    system_component_id: str = None
    state: StepExecutionStatus
    elapsed_time: float
    timestamp: str
    error: str = None
    output_text: str = None
    data: typing.Any = None


class WorkflowFullStateReport(BaseModel):
    """Workflow state report is complete log of workflow execution"""

    workflow_name: str = None
    workflow_version: str = None
    run_id: str = None
    state: WorkflowState
    start_time: int = None
    end_time: int = None
    elapsed_time: float = 0
    last_error: str = None
    execution_log: list[WorkflowStepEvent]
