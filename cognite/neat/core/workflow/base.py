import inspect
import json
import logging
import threading
import time
import traceback
from threading import Event
from typing import Type

import yaml
from cognite.client import CogniteClient
from prometheus_client import Gauge

from cognite.neat.core.data_stores.metrics import NeatMetricsCollector
from cognite.neat.core.exceptions import InvalidWorkFlowError
from cognite.neat.core.utils.utils import retry_decorator
from cognite.neat.core.workflow import cdf_store
from cognite.neat.core.workflow.model import (
    FlowMessage,
    StepExecutionStatus,
    StepType,
    WorkflowConfigItem,
    WorkflowDefinition,
    WorkflowFullStateReport,
    WorkflowStartException,
    WorkflowState,
    WorkflowStepDefinition,
    WorkflowStepEvent,
    WorkflowSystemComponent,
)
from cognite.neat.core.workflow.tasks import WorkflowTaskBuilder

from ..configuration import Config
from ..utils.cdf import CogniteClientConfig
from . import utils
from .step_model import Data
import cognite.neat.steps.steps

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
        self.instance_id = utils.generate_run_id()
        self.run_id = ""
        self.last_error = ""
        self.elapsed_time = 0
        self.start_time = None
        self.end_time = None
        self.execution_log: list[WorkflowStepEvent] = []
        self.workflow_steps: list[WorkflowStepDefinition] = workflow_steps
        self.workflow_system_components: list[WorkflowSystemComponent] = []
        self.configs: list[WorkflowConfigItem] = []
        self.flow_message: FlowMessage = None
        self.task_builder: WorkflowTaskBuilder = None
        self.rules_storage_path = None
        self.data_store_path = None
        self.cdf_store = (
            cdf_store.CdfStore(self.cdf_client, data_set_id=self.default_dataset_id)
            if self.default_dataset_id
            else None
        )
        self.metrics = NeatMetricsCollector(self.name, self.cdf_client)
        self.resume_event = Event()
        self.is_ephemeral = False  # if True, workflow will be deleted after completion
        self.data: dict[str, Type[Data]] = {}

    def start(self, sync=False, is_ephemeral=False, **kwargs) -> FlowMessage | None:
        """Starts workflow execution.sync=True will block until workflow is completed and
        return last workflow flow message, sync=False will start workflow in a separate thread and return None"""
        if self.state not in [WorkflowState.CREATED, WorkflowState.COMPLETED, WorkflowState.FAILED]:
            logging.error(f"Workflow {self.name} is already running")
            return None
        self.state = WorkflowState.RUNNING
        self.start_time = time.time()
        self.end_time = None
        self.run_id = utils.generate_run_id()
        self.is_ephemeral = is_ephemeral
        self.execution_log = []
        if sync:
            return self._run_workflow(**kwargs)

        self.thread = threading.Thread(target=self._run_workflow, kwargs=kwargs)
        self.thread.start()
        return None

    def _run_workflow(self, **kwargs) -> FlowMessage | None:
        """Run workflow and return last workflow flow message"""
        summary_metrics.labels(wf_name=self.name, name="steps_count").set(len(self.workflow_steps))
        logging.info(f"Starting workflow {self.name}")
        if flow_message := kwargs.get("flow_message"):
            self.flow_message = flow_message
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
        if not start_step_id:
            trigger_steps = list(filter(lambda x: x.trigger, self.workflow_steps))
        else:
            trigger_steps = list(filter(lambda x: x.id == start_step_id, self.workflow_steps))

        if not trigger_steps:
            logging.error(f"Workflow {self.name} has no trigger steps or start step {start_step_id} not found")
            return "Workflow has no trigger steps"

        self.execution_log.append(
            WorkflowStepEvent(
                id=trigger_steps[0].id,
                state=StepExecutionStatus.SUCCESS,
                elapsed_time=0,
                timestamp=utils.get_iso8601_timestamp_now_unaware(),
                data=self.flow_message.payload if self.flow_message else None,
            )
        )

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
                        system_component_id=step.system_component_id,
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

    def copy(self) -> "BaseWorkflow":
        """Create a copy of the workflow"""
        new_instance = self.__class__(self.name, self.cdf_client)
        new_instance.workflow_steps = self.workflow_steps
        new_instance.configs = self.configs
        new_instance.set_task_builder(self.task_builder)
        new_instance.set_default_dataset_id(self.default_dataset_id)
        new_instance.set_storage_path("transformation_rules", self.rules_storage_path)
        new_instance.set_storage_path("data_store", self.data_store_path)
        return new_instance

    def run_step(self, step: WorkflowStepDefinition) -> FlowMessage | None:
        step_name = step.id
        system_component_id = step.system_component_id

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
                system_component_id=system_component_id,
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

                @retry_decorator(
                    max_retries=step.max_retries,
                    retry_delay=step.retry_delay,
                    component_name=f"wf step runner , step.id = {step.id}",
                )
                def method_runner():
                    return method(flow_message)

                new_flow_message = method_runner()
            elif step.stype == StepType.STD_STEP:
                for name, step_cls in inspect.getmembers(cognite.neat.steps.steps):
                    logging.debug(f"Checking step {name}")
                    if inspect.isclass(step_cls):
                        if name == step.method:
                            logging.debug(f" match {name}")
                            step_obj = step_cls(self.metrics)
                            step_obj.set_global_configs(self.cdf_client, self.data_store_path, self.rules_storage_path)
                            signature = inspect.signature(step_obj.run)
                            parameters = signature.parameters
                            is_valid = True
                            input_data = []
                            missing_data = []
                            for parameter in parameters.values():
                                try:
                                    if parameter.annotation.__name__ == "FlowMessage":
                                        input_data.append(self.flow_message)
                                    else:    
                                        input_data.append(self.data[parameter.annotation.__name__])
                                except KeyError:
                                    is_valid = False
                                    logging.error(f"Missing data for step {step.id} parameter {parameter.name}")
                                    missing_data.append(parameter.annotation.__name__)
                                    continue
                            if not is_valid:
                                raise InvalidWorkFlowError(step.id, missing_data)
                            output = step_obj.run(*input_data)
                            if output is not None:
                                if isinstance(output, tuple):
                                    for i, out_obj in enumerate(output):
                                        if isinstance(out_obj, FlowMessage):
                                            new_flow_message = out_obj
                                        else:
                                            self.data[type(out_obj).__name__] = out_obj
                                else:
                                    if isinstance(output, FlowMessage):
                                        new_flow_message = output
                                    else:
                                        self.data[output.__name__] = output
                            break

            elif step.stype == StepType.START_WORKFLOW_TASK_STEP:
                if self.task_builder:
                    sync_str = step.params.get("sync", "false")
                    sync = sync_str.lower() == "true" or sync_str == "1"
                    start_status = self.task_builder.start_workflow_task(
                        workflow_name=step.params.get("workflow_name", ""), sync=sync, flow_message=self.flow_message
                    )
                    if start_status.is_success and start_status.workflow_instance.state == WorkflowState.COMPLETED:
                        new_flow_message = start_status.workflow_instance.flow_message
                    else:
                        logging.error(f"Workflow step {step.id} failed to start workflow task")
                        if start_status.is_success:
                            raise WorkflowStartException(start_status.workflow_instance.last_error)
                        else:
                            raise WorkflowStartException(start_status.status_text)

                else:
                    logging.error(f"Workflow step {step.id} has no task builder")
                    raise Exception(f"Workflow step {step.id} has no task builder")
            elif step.stype == StepType.WAIT_FOR_EVENT:
                # Pause workflow execution until event is received
                if self.state != WorkflowState.RUNNING:
                    logging.error(f"Workflow {self.name} is not running , step {step_name} is skipped")
                    raise Exception(f"Workflow {self.name} is not running , step {step_name} is skipped")
                self.state = WorkflowState.RUNNING_WAITING
                timeout = float(step.params.get("wait_timeout", "60"))
                # reporting workflow execution before waiting for event
                # self.report_workflow_execution()
                logging.info(f"Workflow {self.name} is waiting for event")
                self.resume_event.wait(timeout=timeout)
                logging.info(f"Workflow {self.name} resumed after event")
                self.state = WorkflowState.RUNNING
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
            self.last_error = error_text
            traceback.print_exc()
            steps_metrics.labels(wf_name=self.name, step_name=step_name, name="failed_counter").inc()

        self.execution_log.append(
            WorkflowStepEvent(
                id=step_name,
                system_component_id=system_component_id,
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

    def resume_workflow(self, flow_message: FlowMessage, step_id: str = None):
        if step_id:
            if self.current_step != step_id:
                logging.error(f"Workflow {self.name} is not in step {step_id} , resume is skipped")
                return
        self.flow_message = flow_message
        self.execution_log.append(
            WorkflowStepEvent(
                id=step_id,
                state=StepExecutionStatus.SUCCESS,
                elapsed_time=0,
                timestamp=utils.get_iso8601_timestamp_now_unaware(),
                data=self.flow_message.payload,
            )
        )
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
            system_components=self.workflow_system_components,
            configs=self.configs,
        )

    def add_step(self, step: WorkflowStepDefinition):
        self.workflow_steps.append(step)

    def add_system_component(self, system_components: WorkflowSystemComponent):
        self.workflow_system_components.append(system_components)

    def serialize_workflow(self, output_format: str = "json", custom_implementation_module: str = None) -> str:
        workflow_definitions = WorkflowDefinition(
            name=self.name,
            steps=self.workflow_steps,
            system_components=self.workflow_system_components,
            configs=self.configs,
            implementation_module=custom_implementation_module,
        )
        if output_format == "json":
            return json.dumps(workflow_definitions.model_dump(), indent=4)
        elif output_format == "yaml":
            return yaml.dump(workflow_definitions.model_dump(), indent=4)

    @classmethod
    def deserialize_metadata(cls, json_string: str, output_format: str = "json") -> WorkflowDefinition:
        if output_format == "json":
            workflow_definitions = WorkflowDefinition.model_validate(json.loads(json_string))
        elif output_format == "yaml":
            workflow_definitions = WorkflowDefinition.model_validate(yaml.load(json_string, Loader=yaml.Loader))
        else:
            raise NotImplementedError(f"Output format {output_format} is not supported.")
        return workflow_definitions

    def set_metadata(self, metadata: WorkflowDefinition):
        self.workflow_steps = metadata.steps
        self.workflow_system_components = metadata.system_components
        self.configs = metadata.configs

    def set_storage_path(self, storage_type: str, storage_path: str):
        if storage_type == "transformation_rules":
            self.rules_storage_path = storage_path
        elif storage_type == "data_store":
            self.data_store_path = storage_path

    def set_task_builder(self, task_builder: WorkflowTaskBuilder):
        self.task_builder = task_builder

    def get_config_item(self, config_name: str) -> WorkflowConfigItem:
        return next((item for item in self.configs if item.name == config_name), None)

    def get_config_group_values_by_name(self, group_name: str, remove_group_prefix: bool = True) -> dict[str, str]:
        return {
            (item.name.removeprefix(item.group) if remove_group_prefix else item.name): item.value
            for item in self.configs
            if item.group == group_name
        }

    def get_config_item_value(self, config_name: str, default_value=None) -> str | None:
        return config.value if (config := self.get_config_item(config_name)) else default_value

    def set_default_dataset_id(self, default_dataset_id: int):
        self.default_dataset_id = default_dataset_id
        self.cdf_store = (
            cdf_store.CdfStore(self.cdf_client, data_set_id=self.default_dataset_id)
            if self.default_dataset_id
            else None
        )

    def set_cdf_client_config(self, cdf_client_config: CogniteClientConfig):
        """Set the CogniteClient configuration to be used by the workflow to create new CogniteClient instances."""
        self.cdf_client_config = cdf_client_config

    def get_new_cdf_client(self):
        """Get a new CogniteClient instance with the same configuration as the one used by the workflow .
          Should be used from workflow steps to avoid sharing the same client instance between steps or
          reset reference to old client instance.
        Returns: CogniteClient
        """
        return CogniteClient(self.cdf_client_config)

    def get_step_by_id(self, step_id: str) -> WorkflowStepDefinition:
        return next((step for step in self.workflow_steps if step.id == step_id), None)

    def get_trigger_step(self, step_id: str = None) -> WorkflowStepDefinition:
        if step_id:
            return next((step for step in self.workflow_steps if step.id == step_id and step.enabled), None)
        else:
            return next((step for step in self.workflow_steps if step.trigger and step.enabled), None)
