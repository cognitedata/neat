import importlib
import inspect
import logging
import os
import sys
import traceback
from pathlib import Path

from cognite.client import CogniteClient

from cognite.neat.core.workflow import BaseWorkflow
from cognite.neat.core.workflow.base import WorkflowDefinition
from cognite.neat.core.workflow.tasks import WorkflowTaskBuilder


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
        data_set_id: int = None,
    ):
        self.client = client
        self.data_set_id = data_set_id
        self.workflow_registry: dict[str, BaseWorkflow] = {}
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
                except Exception as e:
                    trace = traceback.format_exc()
                    logging.error(f"Error loading workflow {wf_module_name}: error: {e} trace : {trace}")
