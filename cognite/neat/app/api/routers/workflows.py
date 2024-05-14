import logging
import shutil
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from cognite.neat.app.api.configuration import NEAT_APP
from cognite.neat.app.api.data_classes.rest import DownloadFromCdfRequest, RunWorkflowRequest, UploadToCdfRequest
from cognite.neat.workflows import WorkflowFullStateReport
from cognite.neat.workflows.base import WorkflowDefinition
from cognite.neat.workflows.migration.wf_manifests import migrate_wf_manifest
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import DataContract
from cognite.neat.workflows.utils import get_file_hash

router = APIRouter()


@router.post("/api/workflow/start")
def start_workflow(request: RunWorkflowRequest):
    logging.info("Starting workflow endpoint")
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    start_status = NEAT_APP.workflow_manager.start_workflow_instance(
        request.name, sync=request.sync, flow_msg=FlowMessage()
    )
    result = {"workflow_instance": None, "is_success": start_status.is_success, "status_text": start_status.status_text}
    return {"result": result}


@router.get("/api/workflow/stats/{workflow_name}", response_model=WorkflowFullStateReport)
def get_workflow_stats(
    workflow_name: str,
) -> WorkflowFullStateReport | None | dict[str, str]:
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow.get_state()


@router.get("/api/workflow/workflows")
def get_workflows():
    return {"workflows": NEAT_APP.workflow_manager.get_list_of_workflows()}


@router.get("/api/workflow/files/{workflow_name}")
def get_workflow_files(workflow_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return {"files": workflow.get_list_of_workflow_artifacts()}


@router.post("/api/workflow/package/{workflow_name}")
def package_workflow(workflow_name: str):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    package_file = NEAT_APP.cdf_store.package_workflow(workflow_name)
    hash_ = get_file_hash(NEAT_APP.config.workflows_store_path / package_file)
    return {"package": package_file, "hash": hash_}


@router.post("/api/workflow/context-cleanup/{workflow_name}")
def cleanup_workflow_data(workflow_name: str):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is not None:
        workflow.cleanup_workflow_context()
    return {"result": "ok"}


@router.post("/api/workflow/create")
def create_new_workflow(request: WorkflowDefinition):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    new_workflow_definition = NEAT_APP.workflow_manager.create_new_workflow(
        request.name, request.description, "manifest"
    )
    return {"workflow": new_workflow_definition}


@router.delete("/api/workflow/{workflow_name}")
def delete_workflow(workflow_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    NEAT_APP.workflow_manager.delete_workflow(workflow_name)
    return {"result": "ok"}


@router.get("/api/workflow/executions")
def get_list_of_workflow_executions():
    return {"executions": NEAT_APP.cdf_store.get_list_of_workflow_executions_from_cdf()}


@router.get("/api/workflow/detailed-execution-report/{execution_id}")
def get_detailed_execution(execution_id: str):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    return {"report": NEAT_APP.cdf_store.get_detailed_workflow_execution_report_from_cdf(execution_id)}


@router.post("/api/workflow/reload-workflows")
def reload_workflows():
    NEAT_APP.workflow_manager.load_workflows_from_storage()
    NEAT_APP.triggers_manager.reload_all_triggers()
    return {"result": "ok", "workflows": NEAT_APP.workflow_manager.get_list_of_workflows()}


@router.post("/api/workflow/reload-single-workflow/{workflow_name}")
def reload_single_workflows(workflow_name: str):
    NEAT_APP.workflow_manager.load_single_workflow_from_storage(workflow_name)
    NEAT_APP.triggers_manager.reload_all_triggers()
    return {"result": "ok", "workflows": NEAT_APP.workflow_manager.get_list_of_workflows()}


@router.get("/api/workflow/workflow-definition/{workflow_name}")
def get_workflow_definition(workflow_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"error": "Workflow is not initialized"}
    return {"definition": workflow.get_workflow_definition()}


@router.get("/api/workflow/workflow-src/{workflow_name}/{file_name}")
def get_workflow_src(workflow_name: str, file_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    # Todo: Thi sis a bug in the API. The method below does not exist
    src = NEAT_APP.workflow_manager.get_workflow_src(workflow_name, file_name=file_name)  # type: ignore[attr-defined]
    return FileResponse(src, media_type="text/plain")


@router.post("/api/workflow/workflow-definition/{workflow_name}")
def update_workflow_definition(workflow_name: str, request: WorkflowDefinition):
    if NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    wf = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if wf is not None:
        wf.cleanup_workflow_context()
    NEAT_APP.workflow_manager.update_workflow(workflow_name, request)
    NEAT_APP.workflow_manager.save_workflow_to_storage(workflow_name)
    return {"result": "ok"}


@router.post("/api/workflow/upload-wf-to-cdf/{workflow_name}")
def upload_workflow_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    NEAT_APP.cdf_store.save_workflow_to_cdf(
        workflow_name, changed_by=request.author, comments=request.comments, tag=request.tag
    )
    return {"result": "ok"}


@router.post("/api/workflow/upload-rules-cdf/{workflow_name}")
def upload_rules_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    file_path = Path(NEAT_APP.config.rules_store_path, request.file_name)
    NEAT_APP.cdf_store.save_resource_to_cdf(
        workflow_name, "neat-wf-rules", file_path, changed_by=request.author, comments=request.comments
    )
    return {"result": "ok"}


@router.post("/api/workflow/download-wf-from-cdf")
def download_wf_from_cdf(request: DownloadFromCdfRequest):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    NEAT_APP.cdf_store.load_workflows_from_cdf(request.file_name, request.version)
    return {"result": "ok"}


@router.post("/api/workflow/download-rules-from-cdf")
def download_rules_to_cdf(request: DownloadFromCdfRequest):
    if NEAT_APP.cdf_store is None:
        return {"error": "NeatApp is not initialized"}
    NEAT_APP.cdf_store.load_rules_file_from_cdf(request.file_name, request.version)
    return {"file_name": request.file_name, "hash": request.version}


@router.post("/api/workflow/migrate-workflow")
def migrate_workflow():
    return migrate_wf_manifest(NEAT_APP.config.data_store_path)


@router.get("/api/workflow/pre-cdf-assets/{workflow_name}")
def get_pre_cdf_assets(workflow_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "Workflow Manager is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"assets": []}
    return {"assets": workflow.data["CategorizedAssets"]}


@router.get("/api/workflow/context/{workflow_name}")
def get_context(workflow_name: str):
    if NEAT_APP.workflow_manager is None:
        return {"error": "Workflow Manager is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"error": "Workflow is not initialized"}
    context = workflow.get_context()
    objects_in_context = []
    for key, value in context.items():
        objects_in_context.append({"name": key, "type": type(value).__name__})
    return {"context": objects_in_context}


@router.get("/api/workflow/context/{workflow_name}/object_name/{object_name}")
def get_context_object(workflow_name: str, object_name: str):
    """Get context item from workflow. Should be used for debugging and troubleshooting only."""
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return
    context = workflow.get_context()
    if object_name not in context:
        return {"error": f"Item {object_name} is not found in workflow context"}

    if object_name == "SourceGraph" or object_name == "SolutionGraph":
        return {"object": cast(SourceGraph | SolutionGraph, context[object_name]).graph.diagnostic_report()}

    cobject = context[object_name]
    if isinstance(cobject, DataContract):
        return {"object": cobject.model_dump()}
    else:
        return {"object": cobject}


@router.get("/api/workflow/registered-steps")
def get_steps():
    steps_registry = NEAT_APP.workflow_manager.get_steps_registry()
    return {"steps": steps_registry.get_list_of_steps()}


@router.post("/api/workflow/file/{workflow_name}")
async def upload_file(file: UploadFile, workflow_name: str):
    if NEAT_APP.workflow_manager is None or NEAT_APP.workflow_manager.data_store_path is None:
        return JSONResponse(content={"error": "Workflow Manager is not initialized"}, status_code=400)
    try:
        upload_dir = NEAT_APP.workflow_manager.config.workflows_store_path / workflow_name
        # Create a directory to store uploaded files if it doesn't exist

        # Define the file path where the uploaded file will be saved
        if file.filename is None:
            return JSONResponse(content={"message": "File name is not provided"}, status_code=400)
        file_path = upload_dir / file.filename

        # Save the uploaded file to the specified path
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if file.filename.endswith(".py"):
            NEAT_APP.workflow_manager.steps_registry.load_workflow_step_classes(workflow_name)

        return JSONResponse(content={"message": "File uploaded successfully"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"message": f"An error occurred: {e!s}"}, status_code=500)


async def get_body(request: Request):
    return await request.body()


fast_api_depends = Depends(get_body)


@router.post("/api/workflow/{workflow_name}/http_trigger/{step_id}")
def http_trigger_start_workflow(workflow_name: str, step_id: str, request: Request, body: bytes = fast_api_depends):
    if NEAT_APP.triggers_manager is None:
        return JSONResponse(content={"error": "Triggers Manager is not initialized"}, status_code=400)
    return NEAT_APP.triggers_manager.start_workflow_from_http_request(workflow_name, step_id, request, body)


@router.post("/api/workflow/{workflow_name}/resume/{step_id}/{instance_id}")
def http_trigger_resume_workflow(
    workflow_name: str, step_id: str, instance_id: str, request: Request, body: bytes = fast_api_depends
):
    if NEAT_APP.triggers_manager is None:
        return JSONResponse(content={"error": "Triggers Manager is not initialized"}, status_code=400)
    return NEAT_APP.triggers_manager.resume_workflow_from_http_request(
        workflow_name, step_id, instance_id, request, body
    )
