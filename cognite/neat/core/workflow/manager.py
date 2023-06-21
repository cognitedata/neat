import importlib
import inspect
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from cognite.client import CogniteClient
from prometheus_client import Gauge
from pydantic import BaseModel

from cognite.neat.core.workflow import BaseWorkflow
from cognite.neat.core.workflow.base import WorkflowDefinition
from cognite.neat.core.workflow.model import FlowMessage, InstanceStartMethod, WorkflowState
from cognite.neat.core.workflow.tasks import WorkflowTaskBuilder

live_workflow_instances = Gauge("neat_workflow_live_instances", "Count of live workflow instances", ["itype"])


class WorkflowStartStatus(BaseModel):
    workflow_instance: BaseWorkflow = None
    is_success: bool = True
    status_text: str = None

    class Config:
        arbitrary_types_allowed = True


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
        client: CogniteClient = None,
        registry_storage_type: str = "file",
        workflows_storage_path: Path = None,
        rules_storage_path: Path = None,
        data_store_path: Path = None,
        data_set_id: int = None,
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

    def update_cdf_client(self, client: CogniteClient):
        self.client = client
        self.task_builder = WorkflowTaskBuilder(client, self)
        self.workflow_registry = {}
        self.load_workflows_from_storage_v2()

    def get_list_of_workflows(self):
        return list(self.workflow_registry.keys())

    def get_workflow(self, name: str) -> BaseWorkflow:
        return self.workflow_registry[name]

    def start_workflow(self, name: str, sync=False, **kwargs):
        workflow = self.get_workflow(name)
        workflow.start(sync, kwargs=kwargs)
        return workflow

    def delete_workflow(self, name: str):
        del self.workflow_registry[name]
        return

    def update_workflow(self, name: str, workflow: WorkflowDefinition):
        self.workflow_registry[name].workflow_steps = workflow.steps
        self.workflow_registry[name].configs = workflow.configs
        self.workflow_registry[name].workflow_system_components = workflow.system_components
        return

    def save_workflow_to_storage(self, name: str, custom_implementation_module: str = None):
        """Save workflow from memory to storage"""
        if self.workflows_storage_type == "file":
            full_path = self.workflows_storage_path / name / "workflow.yaml"
            wf = self.workflow_registry[name]
            with open(full_path, "w") as f:
                f.write(
                    wf.serialize_workflow(
                        output_format="yaml", custom_implementation_module=custom_implementation_module
                    )
                )

    def load_workflows_from_storage_v2(self, dir_path: str = None):
        """Loads workflows from disk/storage into memory , initializes and register them in the workflow registry"""
        if dir_path:
            dir_path = Path(dir_path)
        else:
            dir_path = self.workflows_storage_path
        sys.path.append(str(dir_path))
        for wf_module_name in os.listdir(dir_path):
            wf_module_full_path = dir_path / wf_module_name
            if wf_module_full_path.is_dir():
                try:
                    logging.info(f"Loading workflow {wf_module_name} from {wf_module_full_path}")
                    # metadata_file = f"{dir_path}//{module_name}.yaml"
                    metadata_file = dir_path / wf_module_name / "workflow.yaml"
                    logging.info(f"Loading workflow {wf_module_name} metadata from {metadata_file}")
                    if os.path.exists(metadata_file):
                        with open(metadata_file, "r") as f:
                            wf_str = f.read()
                            metadata = BaseWorkflow.deserialize_metadata(wf_str, output_format="yaml")
                    else:
                        logging.info(f"Metadata file {metadata_file} not found, skipping")
                        continue

                    if metadata.implementation_module:
                        wf_module_name = metadata.implementation_module
                        logging.info(f"Loading CUSTOM workflow module {wf_module_name}")
                    else:
                        logging.info(f"Loading workflow module {wf_module_name}")

                    full_module_name = f"{wf_module_name}.workflow"
                    if full_module_name in sys.modules:
                        logging.info(f"Reloading existing workflow module {wf_module_name}")
                        module = importlib.reload(sys.modules[full_module_name])
                    else:
                        logging.info(f"Loading NEW workflow module {wf_module_name}")
                        module = importlib.import_module(full_module_name)
                    # dynamically load all classes in the module
                    for name, obj in inspect.getmembers(module):
                        if "NeatWorkflow" not in name:
                            continue
                        logging.info(f"Found class {name} in module {wf_module_name}")
                        if inspect.isclass(obj):
                            self.workflow_registry[wf_module_name] = obj(wf_module_name, self.client)
                            self.workflow_registry[wf_module_name].set_metadata(metadata)
                            self.workflow_registry[wf_module_name].set_task_builder(self.task_builder)
                            self.workflow_registry[wf_module_name].set_default_dataset_id(self.data_set_id)
                            self.workflow_registry[wf_module_name].set_storage_path(
                                "transformation_rules", self.rules_storage_path
                            )
                            self.workflow_registry[wf_module_name].set_storage_path("data_store", self.data_store_path)
                except Exception as e:
                    trace = traceback.format_exc()
                    logging.error(f"Error loading workflow {wf_module_name}: error: {e} trace : {trace}")

    def create_workflow_instance(self, template_name: str, add_to_registry: bool = True) -> BaseWorkflow:
        new_instance = self.workflow_registry[template_name].__class__(template_name, self.client)
        new_instance.workflow_steps = self.workflow_registry[template_name].workflow_steps
        new_instance.configs = self.workflow_registry[template_name].configs
        new_instance.set_task_builder(self.task_builder)
        new_instance.set_default_dataset_id(self.data_set_id)
        new_instance.set_storage_path("transformation_rules", self.rules_storage_path)
        new_instance.set_storage_path("data_store", self.data_store_path)
        if add_to_registry:
            self.ephemeral_instance_registry[new_instance.instance_id] = new_instance
        live_workflow_intances.labels(itype="ephemeral").set(len(self.ephemeral_instance_registry))
        return new_instance

    def get_workflow_instance(self, instance_id: str) -> BaseWorkflow:
        return self.ephemeral_instance_registry[instance_id]

    def delete_workflow_instance(self, instance_id: str):
        del self.ephemeral_instance_registry[instance_id]
        live_workflow_intances.labels(itype="ephemeral").set(len(self.ephemeral_instance_registry))
        return

    def start_workflow_instance(
        self, workflow_name: str, step_id: str = "", flow_msg: FlowMessage = None, sync: bool = None
    ) -> WorkflowStartStatus:
        workflow = self.get_workflow(workflow_name)

        trigger_step = workflow.get_trigger_step(step_id)
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
            live_workflow_intances.labels(itype="persistent").set(len(self.workflow_registry))
            # wait until workflow transition to RUNNING state and then start , set max wait time to 30 seconds
            start_time = time.perf_counter()
            # wait until workflow transition to RUNNING state and then start , set max wait time to 30 seconds.
            # The operation is executed in callers thread
            while workflow.state == WorkflowState.RUNNING:
                logging.info("Existing workflow instance already running , waiting for RUNNING state")
                elapsed_time = time.perf_counter() - start_time
                if elapsed_time > max_wait_time:
                    logging.info(
                        f"Workflow {workflow_name} wait time exceeded . elapsed time = {elapsed_time}, max wait time = {max_wait_time}"
                    )
                    return WorkflowStartStatus(None, False, "Workflow instance already running.Wait time exceeded")
                time.sleep(0.5)
            workflow_instance = workflow.start(sync=sync, flow_message=flow_msg, start_step_id=step_id)
            if workflow_instance:
                return WorkflowStartStatus(workflow_instance=workflow, is_success=True, status_text="")
            else:
                return WorkflowStartStatus(
                    workflow_instance=None,
                    is_success=False,
                    status_text="Something went wrong while starting workflow instance",
                )

        elif instance_start_method == InstanceStartMethod.PERSISTENT_INSTANCE_NON_BLOCKING:
            live_workflow_intances.labels(itype="persistent").set(len(self.workflow_registry))
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
