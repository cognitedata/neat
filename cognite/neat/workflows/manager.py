import importlib
import inspect
import logging
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from cognite.client import CogniteClient
from prometheus_client import Gauge
from pydantic import BaseModel

from cognite.neat.workflows import BaseWorkflow
from cognite.neat.workflows.base import WorkflowDefinition
from cognite.neat.workflows.model import FlowMessage, InstanceStartMethod, WorkflowState
from cognite.neat.workflows.steps_registry import StepsRegistry
from cognite.neat.workflows.tasks import WorkflowTaskBuilder

live_workflow_instances = Gauge("neat_workflow_live_instances", "Count of live workflow instances", ["itype"])


class WorkflowStartStatus(BaseModel, arbitrary_types_allowed=True):
    workflow_instance: BaseWorkflow | None = None
    is_success: bool = True
    status_text: str | None = None


class WorkflowManager:
    """Workflow manager is responsible for loading, saving and managing workflows
    client: CogniteClient
    registry_storage_type: str = "file"
    workflows_storage_path: Path = Path("workflows")
    rules_storage_path: Path = Path("rules")
    data_set_id: int = None,
    """

    def __init__(
        self,
        client: CogniteClient | None = None,
        registry_storage_type: str = "file",
        workflows_storage_path: Path | None = None,
        rules_storage_path: Path | None = None,
        data_store_path: Path | None = None,
        data_set_id: int | None = None,
    ):
        self.client = client
        self.data_set_id = data_set_id
        self.data_store_path = data_store_path
        self.workflow_registry: dict[str, BaseWorkflow] = {}
        self.ephemeral_instance_registry: dict[str, BaseWorkflow] = {}
        self.workflows_storage_type = registry_storage_type
        # todo use pathlib
        self.workflows_storage_path = workflows_storage_path if workflows_storage_path else Path("workflows")
        self.rules_storage_path = rules_storage_path if rules_storage_path else Path("rules")
        self.task_builder = WorkflowTaskBuilder(client, self)
        self.steps_registry = StepsRegistry(self.data_store_path)
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
        del self.workflow_registry[name]
        full_path = self.workflows_storage_path / name
        shutil.rmtree(full_path)
        # TODO: check if more garbage collection is needed here.

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

    def load_workflows_from_storage(self, workflows_storage_path: str | Path | None = None):
        """Loads workflows from disk/storage into memory, initializes and register them in the workflow registry"""

        # set workflow storage path
        workflows_storage_path = Path(workflows_storage_path) if workflows_storage_path else self.workflows_storage_path

        # set system path to be used when importing individual workflows as python modules
        # via importlib.import_module(...)
        sys.path.append(str(workflows_storage_path))

        for workflow_name in os.listdir(workflows_storage_path):
            workflow_path = workflows_storage_path / workflow_name
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
                        continue

                    # This is convinience feature when user wants to share self contained workflow
                    # folder as single zip file.
                    if (workflow_path / "rules").exists():
                        logging.info(f"Copying rules from {workflow_path / 'rules'} to {self.rules_storage_path} ")
                        for rule_file in os.listdir(workflow_path / "rules"):
                            shutil.copy(workflow_path / "rules" / rule_file, self.rules_storage_path)

                    # Comment: All our workflows implementation_module is None
                    # what is this meant for ?, just to have different name?
                    if workflow_definition.implementation_module:
                        workflow_name = workflow_definition.implementation_module
                        logging.info(f"Loading CUSTOM workflow module {workflow_name}")
                    else:
                        logging.info(f"Loading workflow module {workflow_name}")

                    full_module_name = f"{workflow_name}.workflow"
                    load_user_defined_workflow = False
                    if full_module_name in sys.modules:
                        logging.info(f"Reloading existing workflow module {workflow_name}")
                        module = importlib.reload(sys.modules[full_module_name])
                        load_user_defined_workflow = True
                    else:
                        try:
                            module = importlib.import_module(full_module_name)
                            load_user_defined_workflow = True
                            logging.info(f"Workflow implementation class for {workflow_name} loaded successfully")
                        except ModuleNotFoundError:
                            pass

                    self.steps_registry.load_custom_step_classes(workflow_path, workflow_name)
                    # Dynamically load workflow classes which contain "NeatWorkflow" in their name
                    # from workflow.py module in the workflow directory and
                    # Instantiate them using the workflow definition loaded
                    # from workflow.yaml file
                    # WARNING: This will be deprecated in the future.
                    if load_user_defined_workflow:
                        for name, obj in inspect.getmembers(module):
                            if "NeatWorkflow" in name and inspect.isclass(obj):
                                logging.info(
                                    f"Found class {name} in module {workflow_name},"
                                    f" registering it as '{workflow_name}' in the workflow registry"
                                )
                                self.register_workflow(obj, workflow_name, workflow_definition)
                                return
                    else:
                        self.register_workflow(BaseWorkflow, workflow_name, workflow_definition)

                except Exception as e:
                    trace = traceback.format_exc()
                    logging.error(f"Error loading workflow {workflow_name}: error: {e} trace : {trace}")

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
