import logging
import os
import shutil
import sys
import time
import traceback

from cognite.client import CogniteClient
from prometheus_client import Gauge
from pydantic import BaseModel

from cognite.neat._config import Config
from cognite.neat._workflows import BaseWorkflow
from cognite.neat._workflows.base import WorkflowDefinition
from cognite.neat._workflows.model import FlowMessage, InstanceStartMethod, WorkflowState, WorkflowStepDefinition
from cognite.neat._workflows.steps_registry import StepsRegistry
from cognite.neat._workflows.tasks import WorkflowTaskBuilder

live_workflow_instances = Gauge("neat_workflow_live_instances", "Count of live workflow instances", ["itype"])


class WorkflowStartStatus(BaseModel, arbitrary_types_allowed=True):
    workflow_instance: BaseWorkflow | None = None
    is_success: bool = True
    status_text: str | None = None


class WorkflowManager:
    """Workflow manager is responsible for loading, saving and managing workflows
    client: CogniteClient
    config: Config
    """

    def __init__(self, client: CogniteClient, config: Config):
        self.client = client
        self.data_set_id = config.cdf_default_dataset_id
        self.data_store_path = config.data_store_path
        self.workflow_registry: dict[str, BaseWorkflow] = {}
        self.ephemeral_instance_registry: dict[str, BaseWorkflow] = {}
        self.workflows_storage_type = config.workflows_store_type
        self.config = config
        self.workflows_storage_path = config.workflows_store_path
        self.rules_storage_path = config.rules_store_path
        self.task_builder = WorkflowTaskBuilder(client, self)
        self.steps_registry = StepsRegistry(self.config)
        self.steps_registry.load_step_classes()

    def update_cdf_client(self, client: CogniteClient):
        self.client = client
        self.task_builder = WorkflowTaskBuilder(client, self)
        self.workflow_registry = {}
        self.load_workflows_from_storage()

    def get_list_of_workflows(self):
        return list(self.workflow_registry.keys())

    def get_steps_registry(self):
        return self.steps_registry

    def get_workflow(self, name: str) -> BaseWorkflow | None:
        try:
            return self.workflow_registry[name]
        except KeyError:
            return None

    def full_reset(self):
        self.workflow_registry = {}
        self.ephemeral_instance_registry = {}

    def start_workflow(self, name: str, sync=False, **kwargs):
        workflow = self.get_workflow(name)
        if workflow is None:
            raise ValueError(f"Workflow {name} not found")
        workflow.start(sync, kwargs=kwargs)
        return workflow

    def delete_workflow(self, name: str):
        workflow = self.get_workflow(name)
        if workflow is not None:
            workflow.cleanup_workflow_context()
        del self.workflow_registry[name]
        full_path = self.workflows_storage_path / name
        shutil.rmtree(full_path)

    def update_workflow(self, name: str, workflow: WorkflowDefinition):
        self.workflow_registry[name].workflow_steps = workflow.steps
        self.workflow_registry[name].configs = workflow.configs
        self.workflow_registry[name].workflow_system_components = workflow.system_components

    def save_workflow_to_storage(self, name: str, custom_implementation_module: str | None = None):
        """Save workflow from memory to storage"""
        if self.workflows_storage_type == "file":
            full_path = self.workflows_storage_path / name / "workflow.yaml"
            full_path.parent.mkdir(parents=True, exist_ok=True)
            wf = self.workflow_registry[name]
            full_path.write_text(
                wf.serialize_workflow(output_format="yaml", custom_implementation_module=custom_implementation_module)
            )

    def create_new_workflow(self, name: str, description=None, mode: str = "manifest") -> WorkflowDefinition:
        """Create new workflow in memory"""
        workflow_definition = WorkflowDefinition(
            name=name, description=description, steps=[], system_components=[], configs=[]
        )
        self.register_workflow(BaseWorkflow, name, workflow_definition)
        self.save_workflow_to_storage(name)
        return workflow_definition

    def load_single_workflow_from_storage(self, workflow_name: str):
        """Load single workflow from storage into memory"""

        # check if workflow is already loaded. If so, perform context cleanup first
        if workflow_name in self.workflow_registry:
            self.workflow_registry[workflow_name].cleanup_workflow_context()
            del self.workflow_registry[workflow_name]

        workflow_path = self.workflows_storage_path / workflow_name
        # THIS IS WHERE WE LOAD THE WORKFLOW MODULES
        if workflow_path.is_dir():
            logging.info(f"Loading workflow {workflow_name} from {workflow_path}")
            try:
                if (workflow_definition_path := workflow_path / "workflow.yaml").exists():
                    with workflow_definition_path.open() as workflow_definition_file:
                        workflow_definition: WorkflowDefinition = BaseWorkflow.deserialize_definition(
                            workflow_definition_file.read(), output_format="yaml"
                        )
                else:
                    logging.info(f"Definition file {workflow_definition_path} not found, skipping")
                    return

                # This is convinience feature when user wants to share self contained workflow
                # folder as single zip file.
                if (workflow_path / "rules").exists():
                    logging.info(f"Copying rules from {workflow_path / 'rules'} to {self.rules_storage_path} ")
                    for rule_file in os.listdir(workflow_path / "rules"):
                        shutil.copy(workflow_path / "rules" / rule_file, self.rules_storage_path)

                self.steps_registry.load_custom_step_classes(workflow_path, workflow_name)
                self.register_workflow(BaseWorkflow, workflow_name, workflow_definition)

            except Exception as e:
                trace = traceback.format_exc()
                logging.error(f"Error loading workflow {workflow_name}: error: {e} trace : {trace}")

    def load_workflows_from_storage(self):
        """Loads workflows from disk/storage into memory, initializes and register them in the workflow registry"""

        # set workflow storage path
        workflows_storage_path = self.workflows_storage_path

        # set system path to be used when importing individual workflows as python modules
        # via importlib.import_module(...)
        sys.path.append(str(workflows_storage_path))

        for workflow_name in os.listdir(workflows_storage_path):
            self.load_single_workflow_from_storage(workflow_name)

    def register_workflow(self, obj, workflow_name, workflow_definition):
        """Register workflow in the workflow registry

        Parameters
        ----------
        obj : BaseWorkflow
            Class of the workflow to be registered
        workflow_name : _type_
            Name of the workflow to be registered
        workflow_definition : _type_
            Definition of the workflow to be registered originating from workflow.yaml
        """
        self.workflow_registry[workflow_name] = obj(workflow_name, self.client, steps_registry=self.steps_registry)
        self.workflow_registry[workflow_name].set_definition(workflow_definition)
        # Comment: Not entirely sure what is task_builder meant for
        # as at first glance it looks like circular import ???
        self.workflow_registry[workflow_name].set_task_builder(self.task_builder)
        self.workflow_registry[workflow_name].set_default_dataset_id(self.data_set_id)
        self.workflow_registry[workflow_name].set_storage_path("transformation_rules", self.rules_storage_path)
        self.workflow_registry[workflow_name].set_storage_path("data_store", self.data_store_path)

    def create_workflow_instance(self, template_name: str, add_to_registry: bool = True) -> BaseWorkflow:
        new_instance = self.workflow_registry[template_name].copy()
        if add_to_registry:
            self.ephemeral_instance_registry[new_instance.instance_id] = new_instance
        live_workflow_instances.labels(itype="ephemeral").set(len(self.ephemeral_instance_registry))
        return new_instance

    def get_workflow_instance(self, instance_id: str) -> BaseWorkflow:
        return self.ephemeral_instance_registry[instance_id]

    def delete_workflow_instance(self, instance_id: str):
        del self.ephemeral_instance_registry[instance_id]
        live_workflow_instances.labels(itype="ephemeral").set(len(self.ephemeral_instance_registry))
        return

    def start_workflow_instance(
        self, workflow_name: str, step_id: str = "", flow_msg: FlowMessage | None = None, sync: bool | None = None
    ) -> WorkflowStartStatus:
        retrieved = self.get_workflow(workflow_name)

        if retrieved is None:
            return WorkflowStartStatus(
                workflow_instance=None, is_success=False, status_text="Workflow not found in registry"
            )

        if self._is_workflow_made_of_mixed_steps(retrieved.workflow_steps):
            retrieved.state = WorkflowState.FAILED
            return WorkflowStartStatus(
                workflow_instance=None,
                is_success=False,
                status_text="Workflow consists of both legacy and current steps. "
                "Please update the workflow to use only current steps.",
            )

        workflow = retrieved
        retrieved_step = workflow.get_trigger_step(step_id)
        if retrieved_step is None:
            return WorkflowStartStatus(
                workflow_instance=None, is_success=False, status_text="Step not found in workflow"
            )
        trigger_step = retrieved_step
        if not trigger_step.trigger:
            logging.info(f"Step {step_id} is not a trigger step")
            return WorkflowStartStatus(
                workflow_instance=None, is_success=False, status_text="Step is not a trigger step"
            )
        if sync is None:
            sync = trigger_step.params.get("sync", "true").lower() == "true"

        max_wait_time = int(trigger_step.params.get("max_wait_time", "30"))
        instance_start_method = trigger_step.params.get(
            "workflow_start_method", InstanceStartMethod.PERSISTENT_INSTANCE_BLOCKING
        )

        logging.info(
            f"""----- Starting workflow {workflow_name} , step_id = {step_id} , sync = {sync},
              max_wait_time = {max_wait_time}, instance_start_method = {instance_start_method} -----"""
        )

        if instance_start_method == InstanceStartMethod.PERSISTENT_INSTANCE_BLOCKING:
            live_workflow_instances.labels(itype="persistent").set(len(self.workflow_registry))
            # wait until workflow transition to RUNNING state and then start , set max wait time to 30 seconds
            start_time = time.perf_counter()
            # wait until workflow transition to RUNNING state and then start , set max wait time to 30 seconds.
            # The operation is executed in callers thread
            while workflow.state == WorkflowState.RUNNING:
                logging.info("Existing workflow instance already running , waiting for RUNNING state")
                elapsed_time = time.perf_counter() - start_time
                if elapsed_time > max_wait_time:
                    logging.info(
                        f"Workflow {workflow_name} wait time exceeded . "
                        f"elapsed time = {elapsed_time}, max wait time = {max_wait_time}"
                    )
                    return WorkflowStartStatus(
                        workflow_instance=None,
                        is_success=False,
                        status_text="Workflow instance already running.Wait time exceeded",
                    )
                time.sleep(0.5)
            workflow.start(sync=sync, flow_message=flow_msg, start_step_id=step_id)
            return WorkflowStartStatus(workflow_instance=workflow, is_success=True, status_text="")

        elif instance_start_method == InstanceStartMethod.PERSISTENT_INSTANCE_NON_BLOCKING:
            live_workflow_instances.labels(itype="persistent").set(len(self.workflow_registry))
            # start workflow if not already running, skip if already running
            if workflow.state == WorkflowState.RUNNING:
                return WorkflowStartStatus(
                    workflow_instance=None, is_success=False, status_text="Workflow instance already running"
                )

            workflow.start(sync=sync, flow_message=flow_msg, start_step_id=step_id)
            return WorkflowStartStatus(workflow_instance=workflow, is_success=True, status_text="")

        elif instance_start_method == InstanceStartMethod.EPHEMERAL_INSTANCE:
            # start new workflow instance in new thread
            workflow = self.create_workflow_instance(workflow_name, add_to_registry=True)
            workflow.start(sync=sync, delete_after_completion=True, flow_message=flow_msg, start_step_id=step_id)
            if sync:
                self.delete_workflow_instance(workflow.instance_id)
            return WorkflowStartStatus(workflow_instance=workflow, is_success=True, status_text="")

        return WorkflowStartStatus(
            workflow_instance=None, is_success=False, status_text="Unsupported workflow start method"
        )

    def _is_workflow_made_of_mixed_steps(self, steps: list[WorkflowStepDefinition]):
        legacy_steps = 0
        current_steps = 0
        for step in steps:
            if step.method in self.steps_registry.categorized_steps["legacy"]:
                legacy_steps += 1
            if step.method in self.steps_registry.categorized_steps["current"]:
                current_steps += 1
        return legacy_steps > 0 and current_steps > 0
