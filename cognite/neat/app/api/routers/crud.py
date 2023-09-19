# IO, CDF, Workflows


import logging
import shutil

from fastapi import APIRouter, UploadFile

from cognite.neat.app.api.configuration import neat_app
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.utils import get_file_hash

router = APIRouter()


@router.get("/api/cdf/neat-resources")
def get_neat_resources(resource_type: str | None = None):
    result = neat_app.cdf_store.get_list_of_resources_from_cdf(resource_type=resource_type)
    logging.debug(f"Got {len(result)} resources")
    return {"result": result}


@router.post("/api/cdf/init-neat-resources")
def init_neat_cdf_resources(resource_type: str | None = None):
    neat_app.cdf_store.init_cdf_resources(resource_type=resource_type)
    return {"result": "ok"}


@router.post("/api/file/upload/{workflow_name}/{file_type}/{step_id}/{action}")
async def file_upload_handler(files: list[UploadFile], workflow_name: str, file_type: str, step_id: str, action: str):
    # get directory path
    upload_dir = neat_app.config.rules_store_path
    file_name = ""
    file_version = ""
    if file_type == "file_from_editor":
        upload_dir = neat_app.workflow_manager.data_store_path / "workflows" / workflow_name
    for file in files:
        logging.info(
            f"Uploading file : {file.filename} , workflow : {workflow_name} , step_id {step_id} , action : {action}"
        )
        # save file to disk
        full_path = upload_dir / file.filename
        with full_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_name = file.filename
        file_version = get_file_hash(full_path)
        break  # only one file is supported for now

    if "update_config" in action and file_type == "rules":
        logging.info("Automatically updating workflow config")
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        workflow_definition = workflow.get_workflow_definition()

        for step in workflow_definition.steps:
            if step.method == "LoadTransformationRules":
                step.configs["file_name"] = file_name
                step.configs["version"] = ""

        neat_app.workflow_manager.save_workflow_to_storage(workflow_name)

    if "start_workflow" in action and file_type == "rules":
        logging.info("Starting workflow after file upload")
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        flow_msg = FlowMessage(
            payload={"file_name": file_name, "hash": file_version, "full_path": full_path, "file_type": file_type}
        )
        start_step_id = None if step_id == "none" else step_id

        workflow.start(sync=False, flow_message=flow_msg, start_step_id=start_step_id)

    return {"file_name": file_name, "hash": file_version}

