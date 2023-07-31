# IO, CDF, Workflows


import logging
import os
import shutil
from fastapi import APIRouter, UploadFile
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem

from cognite.neat.workflows.utils import get_file_hash
from cognite.neat.app.api.configuration import neat_app

router = APIRouter()


@router.get("/api/cdf/neat-resources")
def get_neat_resources(resource_type: str = None):
    result = neat_app.cdf_store.get_list_of_resources_from_cdf(resource_type=resource_type)
    logging.debug(f"Got {len(result)} resources")
    return {"result": result}


@router.post("/api/cdf/init-neat-resources")
def init_neat_cdf_resources(resource_type: str = None):
    neat_app.cdf_store.init_cdf_resources(resource_type=resource_type)
    return {"result": "ok"}


@router.post("/api/file/upload/{workflow_name}/{file_type}/{step_id}/{action}")
async def file_upload_handler(files: list[UploadFile], workflow_name: str, file_type: str, step_id: str, action: str):
    # get directory path
    upload_dir = neat_app.config.rules_store_path
    file_name = ""
    file_version = ""
    for file in files:
        logging.info(
            f"Uploading file : {file.filename} , workflow : {workflow_name} , step_id {step_id} , action : {action}"
        )
        # save file to disk
        full_path = os.path.join(upload_dir, file.filename)
        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_name = file.filename
        file_version = get_file_hash(full_path)
        break  # only one file is supported for now

    if "update_config" in action and file_type == "rules":
        logging.info("Automatically updating workflow config")
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        workflow_definition = workflow.get_workflow_definition()

        # update config item rules.file with the new file name
        config_item = workflow_definition.get_config_item("rules.file")
        if config_item is None:
            config_item = WorkflowConfigItem(name="rules.file", value=file_name, label="Rules file name", group="rules")
        config_item.value = file_name
        workflow_definition.upsert_config_item(config_item)
        # update config item rules.file with the new file name
        config_item = workflow_definition.get_config_item("rules.version")
        if config_item is None:
            config_item = WorkflowConfigItem(name="rules.version", value="", label="Rules file version", group="rules")
            workflow_definition.upsert_config_item(config_item)
        neat_app.workflow_manager.save_workflow_to_storage(workflow_name)

    if "start_workflow" in action:
        logging.info("Starting workflow after file upload")
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        flow_msg = FlowMessage(
            payload={"file_name": file_name, "hash": file_version, "full_path": full_path, "file_type": file_type}
        )
        start_step_id = None if step_id == "none" else step_id

        workflow.start(sync=False, flow_message=flow_msg, start_step_id=start_step_id)

    return {"file_name": file_name, "hash": file_version}
