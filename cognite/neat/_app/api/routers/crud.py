# IO, CDF, Workflows


import logging
import shutil

from fastapi import APIRouter, UploadFile

from cognite.neat._app.api.configuration import NEAT_APP
from cognite.neat._config import Config
from cognite.neat._workflows.model import FlowMessage
from cognite.neat._workflows.utils import get_file_hash

router = APIRouter()


@router.post("/api/file/upload/{workflow_name}/{file_type}/{step_id}/{action}")
async def file_upload_handler(
    files: list[UploadFile],
    workflow_name: str,
    file_type: str,
    step_id: str,
    action: str,
) -> dict[str, str]:
    if NEAT_APP.cdf_store is None or NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    if NEAT_APP.workflow_manager.data_store_path is None:
        return {"error": "Workflow Manager is not initialized"}

    # get directory path
    upload_dir = NEAT_APP.config.rules_store_path
    file_name = ""
    file_version = ""
    if file_type == "file_from_editor":
        upload_dir = NEAT_APP.workflow_manager.config.workflows_store_path / workflow_name
    elif file_type == "workflow":
        upload_dir = NEAT_APP.workflow_manager.config.workflows_store_path
    elif file_type == "staging":
        upload_dir = NEAT_APP.workflow_manager.config.staging_path
    elif file_type == "source_graph":
        upload_dir = NEAT_APP.workflow_manager.config.source_graph_path

    for file in files:
        logging.info(
            f"Uploading file : {file.filename} , workflow : {workflow_name} , step_id {step_id} , action : {action}"
        )
        # save file to disk
        if file.filename:
            if file_type == "global_config":
                full_path = NEAT_APP.config.data_store_path / "config.yaml"
            else:
                full_path = upload_dir / file.filename
            with full_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_name = file.filename
            file_version = get_file_hash(full_path)
        break  # only one file is supported for now

    if "update_config" in action and file_type == "rules":
        logging.info("Automatically updating workflow config")
        workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
        if workflow is None:
            return {"error": f"Workflow {workflow_name} not found"}
        workflow_definition = workflow.get_workflow_definition()

        for step in workflow_definition.steps:
            if step.method == "ImportExcelToRules":
                step.configs["file_name"] = file_name
                step.configs["version"] = ""

        NEAT_APP.workflow_manager.save_workflow_to_storage(workflow_name)

    if "start_workflow" in action and file_type == "rules" or file_type == "staging":
        logging.info("Starting workflow after file upload")
        workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
        if workflow is None:
            return {"error": f"Workflow {workflow_name} not found"}
        flow_msg = FlowMessage(
            payload={
                "file_name": file_name,
                "hash": file_version,
                "full_path": full_path,
                "file_type": file_type,
            }
        )
        start_step_id = None if step_id == "none" else step_id

        workflow.start(sync=False, flow_message=flow_msg, start_step_id=start_step_id)

    if action == "install" and file_type == "workflow":
        logging.info("Installing workflow after file upload")
        NEAT_APP.cdf_store.extract_workflow_package(file_name)

    if file_type == "global_config":
        logging.info("Updating global config and restarting NeatApp")
        config = Config.from_yaml(full_path)
        config.data_store_path = NEAT_APP.config.data_store_path
        NEAT_APP.stop()
        NEAT_APP.start(config=config)
        logging.info("NeatApp restarted")

    return {"file_name": file_name, "hash": file_version}
