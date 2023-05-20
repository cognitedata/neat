import json
import logging
import threading
import time
import traceback

import yaml
from cognite.client import ClientConfig as CogniteClientConfig
from cognite.client import CogniteClient
from prometheus_client import Gauge

from cognite.neat.core.data_classes.config import ClientConfig, Config
from cognite.neat.core.data_stores.metrics import NeatMetricsCollector
from cognite.neat.core.workflow import cdf_store
from cognite.neat.core.workflow.model import (
    FlowMessage,
    StepExecutionStatus,
    StepType,
    WorkflowConfigItem,
    WorkflowDefinition,
    WorkflowFullStateReport,
    WorkflowState,
    WorkflowStepDefinition,
    WorkflowStepEvent,
    WorkflowStepsGroup,
)
from cognite.neat.core.workflow.tasks import WorkflowTaskBuilder
from threading import Event

from . import utils

summary_metrics = Gauge("neat_workflow_summary_metrics", "Workflow execution summary metrics", ["wf_name", "name"])
steps_metrics = Gauge("neat_workflow_steps_metrics", "Workflow step level metrics", ["wf_name", "step_name", "name"])
timing_metrics = Gauge("neat_workflow_timing_metrics", "Workflow timing metrics", ["wf_name", "component", "name"])


class BaseWorkflow:
    def __init__(
        self,
        name: str,
        client: CogniteClient,
        workflow_steps: list[WorkflowStepDefinition] = None,
        default_dataset_id: int = None,
    ):
        self.name = name
        self.module_name = self.__class__.__module__
        self.cdf_client = client
        self.cdf_client_config: CogniteClientConfig = client.config
        self.default_dataset_id = default_dataset_id
        self.state = WorkflowState.CREATED
        self.run_id = ""
        self.last_error = ""
        self.elapsed_time = 0
        self.start_time = None
        self.end_time = None
        self.execution_log: list[WorkflowStepEvent] = []
        self.workflow_steps: list[WorkflowStepDefinition] = workflow_steps
        self.workflow_step_groups: list[WorkflowStepsGroup] = []
        self.configs: list[WorkflowConfigItem] = []
        self.flow_message: FlowMessage = None
        self.task_builder: WorkflowTaskBuilder = None
        self.rules_storage_path = None
        self.cdf_store = (
            cdf_store.CdfStore(self.cdf_client, data_set_id=self.default_dataset_id)
            if self.default_dataset_id
            else None
        )
        self.metrics = NeatMetricsCollector(self.name, self.cdf_client)
        self.resume_event = Event()
        
    def start(self, sync=False, **kwargs) -> FlowMessage | None:
        """Starts workflow execution.sync=True will block until workflow is completed and return last workflow flow message,
        sync=False will start workflow in a separate thread and return None"""
        self.execution_log = []
        if sync:
            return self._run_workflow(**kwargs)

        self.thread = threading.Thread(target=self._run_workflow, kwargs=kwargs)
        self.thread.start()
        return None
    
    def _run_workflow(self, **kwargs) -> FlowMessage | None:
        """Run workflow and return last workflow flow message"""
        summary_metrics.labels(wf_name=self.name, name="steps_count").set(len(self.workflow_steps))
        if self.state not in [WorkflowState.CREATED, WorkflowState.COMPLETED, WorkflowState.FAILED]:
            logging.error(f"Workflow {self.name} is already running")
            return None
        logging.info(f"Starting workflow {self.name}")

        if flow_message := kwargs.get("flow_message"):
            self.flow_message = flow_message

        self.state = WorkflowState.RUNNING
        self.start_time = time.time()
        self.end_time = None
        self.run_id = utils.generate_run_id()
        start_time = time.perf_counter()
        self.report_workflow_execution()
        try:
            start_step_id = kwargs.get("start_step_id")
            logging.info(f"  starting workflow from step {start_step_id}")

            self.run_workflow_steps(start_step_id=start_step_id)
            if self.state == WorkflowState.RUNNING:
                self.state = WorkflowState.COMPLETED
            summary_metrics.labels(wf_name=self.name, name="wf_completed_counter").inc()
        except Exception:
            trace = traceback.format_exc()
            self.last_error = str(trace)
            self.state = WorkflowState.FAILED
            logging.error(f"Workflow failed with error {trace}")
            summary_metrics.labels(wf_name=self.name, name="wf_failed_counter").inc()

        self.elapsed_time = time.perf_counter() - start_time
        self.end_time = time.time()
        timing_metrics.labels(wf_name=self.name, component="workflow", name="workflow").set(self.elapsed_time)
        logging.info(f"Workflow completed in {self.elapsed_time} seconds")
        self.report_workflow_execution()
        return self.flow_message

    def get_transition_step(self, transitions: list[str]) -> list[str]:
        return [stp for stp in self.workflow_steps if stp.id in transitions and stp.enabled] if transitions else []

    def run_workflow_steps(self, start_step_id: str = None) -> str:
        if start_step_id is None:
            trigger_steps = list(filter(lambda x: x.trigger, self.workflow_steps))
        else:
            trigger_steps = list(filter(lambda x: x.id == start_step_id, self.workflow_steps))

        if not trigger_steps:
            logging.error(f"Workflow {self.name} has no trigger steps")
            return "Workflow has no trigger steps"

        step: WorkflowStepDefinition = trigger_steps[0]

        transition_steps = self.get_transition_step(step.transition_to)

        if len(transition_steps) == 0:
            logging.error(f"Workflow {self.name} has no transition steps from step {step.id}")
            return "Workflow has no transition steps"

        step = transition_steps[0]

        for _ in range(
            1000
        ):  # Max 1000 steps in a workflow is a reasonable limit and protection against infinite loops
            new_flow_msg = None
            if step.enabled:
                new_flow_msg = self.run_step(step)
            else:
                logging.info(f"Skipping step workflow step {step.id}")
                self.execution_log.append(
                    WorkflowStepEvent(
                        id=step.id,
                        group_id=step.group_id,
                        state=StepExecutionStatus.SKIPPED,
                        elapsed_time=0,
                        timestamp=utils.get_iso8601_timestamp_now_unaware(),
                        error="",
                    )
                )

            steps = self.get_transition_step(step.transition_to)

            if new_flow_msg:
                # If the step returned a new flow message, use it to mutate execution flow
                if new_flow_msg.next_step_ids:
                    steps = self.get_transition_step(new_flow_msg.next_step_ids)
                self.flow_message = new_flow_msg

            if len(steps) == 0:
                break
            step = steps[0]
            logging.debug(f"Transitioning to step {step.id}")

        return "ok"

    def configure(self, config: Config):
        raise NotImplementedError()

    def run_step(self, step: WorkflowStepDefinition) -> FlowMessage | None:
        step_name = step.id
        group_id = step.group_id

        steps_metrics.labels(wf_name=self.name, step_name=step_name, name="step_started_counter").inc()
        flow_message = self.flow_message
        if self.state != WorkflowState.RUNNING:
            logging.error(f"Workflow {self.name} is not running , step {step_name} is skipped")
            return

        logging.info(f"Running step {step_name}")
        self.current_step = step_name
        start_time = time.perf_counter()
        stop_time = start_time
        step_execution_status = StepExecutionStatus.STARTED
        self.execution_log.append(
            WorkflowStepEvent(
                id=step_name,
                group_id=group_id,
                state=step_execution_status,
                elapsed_time=0,
                timestamp=utils.get_iso8601_timestamp_now_unaware(),
                error="",
            )
        )
        output_text = ""
        error_text = ""
        new_flow_message = None
        try:
            if step.stype == StepType.PYSTEP:
                if step.method and hasattr(self, step.method):
                    method = getattr(self, step.method)
                else:
                    method_name = f"step_{step.id}"
                    if hasattr(self, method_name):
                        method = getattr(self, method_name)
                    else:
                        logging.error(f"Workflow step {step.id} has no method {method_name}")
                        raise Exception(f"Workflow step {step.id} has no method {method_name}")
                new_flow_message = method(flow_message)
            elif step.stype == StepType.START_WORKFLOW_TASK_STEP:
                if self.task_builder:
                    sync_str = step.params.get("sync", "false")
                    sync = sync_str.lower() == "true" or sync_str == "1"
                    new_flow_message = self.task_builder.start_workflow_task(
                        workflow_name=step.params.get("workflow_name", ""), sync=sync, flow_message=self.flow_message
                    )
                else:
                    logging.error(f"Workflow step {step.id} has no task builder")
                    raise Exception(f"Workflow step {step.id} has no task builder")
            elif step.stype == StepType.WAIT_FOR_EVENT:
                # Pause workflow execution until event is received
                self.workflow_state = WorkflowState.RUNNING_WAITING
                timeout = float(step.params.get("timeout", "600"))
                # reporting workflow execution before waiting for event
                self.report_workflow_execution()
                self.resume_event.wait(timeout=timeout)
                logging.info(f"Workflow {self.name} resumed after event")
                self.workflow_state = WorkflowState.RUNNING
                self.resume_event.clear()

            else:
                logging.error(f"Workflow step {step.id} has unsupported step type {step.stype}")

            stop_time = time.perf_counter()
            elapsed_time = stop_time - start_time
            logging.info(f"Step {step_name} completed in {elapsed_time} seconds")
            step_execution_status = StepExecutionStatus.SUCCESS
            if new_flow_message:
                error_text = new_flow_message.error_text
                output_text = new_flow_message.output_text
            steps_metrics.labels(wf_name=self.name, step_name=step_name, name="completed_counter").inc()
            timing_metrics.labels(wf_name=self.name, component="step", name=step_name).set(elapsed_time)
        except Exception:
            self.state = WorkflowState.FAILED
            step_execution_status = StepExecutionStatus.FAILED
            trace = traceback.format_exc()
            elapsed_time = stop_time - start_time
            logging.error(f"Step {step_name} failed with error : {trace}")
            error_text = str(trace)
            traceback.print_exc()
            steps_metrics.labels(wf_name=self.name, step_name=step_name, name="failed_counter").inc()

        self.execution_log.append(
            WorkflowStepEvent(
                id=step_name,
                group_id=group_id,
                state=step_execution_status,
                elapsed_time=round(elapsed_time, 3),
                timestamp=utils.get_iso8601_timestamp_now_unaware(),
                error=error_text,
                output_text=output_text,
                data=new_flow_message.payload if new_flow_message else None,
            )
        )
        if new_flow_message:
            self.flow_message = new_flow_message

        self.report_step_execution()
        return new_flow_message

    def resume_workflow(self, flow_message: FlowMessage):
        self.flow_message = flow_message
        self.resume_event.set()

    def report_step_execution(self):
        pass

    def report_workflow_execution(self):
        reporting_type = "all_enabled"
        if config_item := self.get_config_item("system.execution_reporting_type"):
            reporting_type = config_item.value
        if reporting_type == "all_disabled":
            return
        if self.cdf_store:
            logging.debug("Reporting workflow execution to CDF")
            try:
                self.cdf_store.report_workflow_execution_to_cdf(self.get_state())
            except Exception:
                logging.error("Failed to report workflow execution to CDF")
                traceback.print_exc()

    def get_state(self):
        return WorkflowFullStateReport(
            workflow_name=self.name,
            state=self.state,
            run_id=self.run_id,
            start_time=self.start_time,
            end_time=self.end_time,
            elapsed_time=round(self.elapsed_time, 3),
            last_error=self.last_error,
            execution_log=self.execution_log,
        )

    def set_cognite_client(self, client: CogniteClient):
        self.cdf_client = client

    def get_workflow_definition(self):
        return WorkflowDefinition(
            name=self.name,
            steps=self.workflow_steps,
            groups=self.workflow_step_groups,
            configs=self.configs,
        )

    def add_step(self, step: WorkflowStepDefinition):
        self.workflow_steps.append(step)

    def add_group(self, group: WorkflowStepsGroup):
        self.workflow_step_groups.append(group)

    def serialize_workflow(self, output_format: str = "json", custom_implementation_module: str = None) -> str:
        workflow_definitions = WorkflowDefinition(
            name=self.name,
            steps=self.workflow_steps,
            groups=self.workflow_step_groups,
            configs=self.configs,
            implementation_module=custom_implementation_module,
        )
        if output_format == "json":
            return json.dumps(workflow_definitions.dict(), indent=4)
        elif output_format == "yaml":
            return yaml.dump(workflow_definitions.dict(), indent=4)

    @classmethod
    def deserialize_metadata(cls, json_string: str, output_format: str = "json") -> WorkflowDefinition:
        if output_format == "json":
            workflow_definitions = WorkflowDefinition.parse_raw(json_string)
        elif output_format == "yaml":
            workflow_definitions = WorkflowDefinition.parse_obj(yaml.load(json_string, Loader=yaml.Loader))
        else:
            raise NotImplementedError(f"Output format {output_format} is not supported.")
        return workflow_definitions

    def set_metadata(self, metadata: WorkflowDefinition):
        self.workflow_steps = metadata.steps
        self.workflow_step_groups = metadata.groups
        self.configs = metadata.configs

    def set_storage_path(self, storage_type: str, storage_path: str):
        if storage_type == "transformation_rules":
            self.rules_storage_path = storage_path

    def set_task_builder(self, task_builder: WorkflowTaskBuilder):
        self.task_builder = task_builder

    def get_config_item(self, config_name: str) -> WorkflowConfigItem:
        return next((item for item in self.configs if item.name == config_name), None)

    def get_config_item_value(self, config_name: str, default_value=None) -> str | None:
        return config.value if (config := self.get_config_item(config_name)) else default_value

    def set_default_dataset_id(self, default_dataset_id: int):
        self.default_dataset_id = default_dataset_id
        self.cdf_store = (
            cdf_store.CdfStore(self.cdf_client, data_set_id=self.default_dataset_id)
            if self.default_dataset_id
            else None
        )

    def set_cdf_client_config(self, cdf_client_config: ClientConfig):
        """Set the CogniteClient configuration to be used by the workflow to create new CogniteClient instances."""
        self.cdf_client_config = cdf_client_config

    def get_new_cdf_client(self):
        """Get a new CogniteClient instance with the same configuration as the one used by the workflow .
          Should be used from workflow steps to avoid sharing the same client instance between steps or reset reference to old client instance.
        Returns: CogniteClient
        """
        return CogniteClient(self.cdf_client_config)
