import logging
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from cognite.neat.app.api.configuration import neat_app
from cognite.neat.app.api.data_classes.rest import DownloadFromCdfRequest, RunWorkflowRequest, UploadToCdfRequest
from cognite.neat.workflows import WorkflowFullStateReport
from cognite.neat.workflows import utils
from cognite.neat.workflows.base import WorkflowDefinition
from cognite.neat.workflows.migration.wf_manifests import migrate_wf_manifest
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem


router = APIRouter()


@router.post("/api/workflow/start")
def start_workflow(request: RunWorkflowRequest):
    logging.info("Starting workflow endpoint")
    start_status = neat_app.workflow_manager.start_workflow_instance(
        request.name, sync=request.sync, flow_msg=FlowMessage()
    )
    result = {"workflow_instance": None, "is_success": start_status.is_success, "status_text": start_status.status_text}
    return {"result": result}


@router.get("/api/workflow/stats/{workflow_name}", response_model=WorkflowFullStateReport)
def get_workflow_stats(
    workflow_name: str,
) -> WorkflowFullStateReport:
    logging.info("Hit the get_workflow_stats endpoint")
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    return workflow.get_state()


@router.get("/api/workflow/workflows")
def get_workflows():
    return {"workflows": neat_app.workflow_manager.get_list_of_workflows()}


@router.get("/api/workflow/executions")
def get_list_of_workflow_executions():
    return {"executions": neat_app.cdf_store.get_list_of_workflow_executions_from_cdf()}


@router.get("/api/workflow/detailed-execution-report/{execution_id}")
def get_detailed_execution(execution_id: str):
    return {"report": neat_app.cdf_store.get_detailed_workflow_execution_report_from_cdf(execution_id)}


@router.post("/api/workflow/reload-workflows")
def reload_workflows():
    neat_app.workflow_manager.load_workflows_from_storage()
    neat_app.triggers_manager.reload_all_triggers()
    return {"result": "ok", "workflows": neat_app.workflow_manager.get_list_of_workflows()}


@router.get("/api/workflow/workflow-definition/{workflow_name}")
def get_workflow_definition(workflow_name: str):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    return {"definition": workflow.get_workflow_definition()}


@router.get("/api/workflow/workflow-src/{workflow_name}/{file_name}")
def get_workflow_src(workflow_name: str, file_name: str):
    src = neat_app.workflow_manager.get_workflow_src(workflow_name, file_name=file_name)
    return FileResponse(src, media_type="text/plain")


@router.post("/api/workflow/workflow-definition/{workflow_name}")
def update_workflow_definition(workflow_name: str, request: WorkflowDefinition):
    neat_app.workflow_manager.update_workflow(workflow_name, request)
    neat_app.workflow_manager.save_workflow_to_storage(workflow_name)
    return {"result": "ok"}


@router.post("/api/workflow/upload-wf-to-cdf/{workflow_name}")
def upload_workflow_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    neat_app.cdf_store.save_workflow_to_cdf(
        workflow_name, changed_by=request.author, comments=request.comments, tag=request.tag
    )
    return {"result": "ok"}


@router.post("/api/workflow/upload-rules-cdf/{workflow_name}")
def upload_rules_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    file_path = Path(neat_app.config.rules_store_path, request.file_name)
    neat_app.cdf_store.save_resource_to_cdf(
        workflow_name, "neat-wf-rules", file_path, changed_by=request.author, comments=request.comments
    )
    return {"result": "ok"}


@router.post("/api/workflow/download-wf-from-cdf")
def download_wf_from_cdf(request: DownloadFromCdfRequest):
    neat_app.cdf_store.load_workflows_from_cdf(request.file_name, request.version)
    return {"result": "ok"}


@router.post("/api/workflow/download-rules-from-cdf")
def download_rules_to_cdf(request: DownloadFromCdfRequest):
    neat_app.cdf_store.load_rules_file_from_cdf(request.file_name, request.version)
    return {"file_name": request.file_name, "hash": request.version}


@router.post("/api/workflow/migrate-workflow")
def migrate_workflow():
    return migrate_wf_manifest(neat_app.config.data_store_path)


@router.get("/api/workflow/pre-cdf-assets/{workflow_name}")
def get_pre_cdf_assets(workflow_name: str):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"assets": []}
    return {"assets": workflow.categorized_assets}
