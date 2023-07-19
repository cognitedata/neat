import logging
import os
import shutil
import time
import traceback
from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path

import pkg_resources
import rdflib
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import REGISTRY, Counter, make_asgi_app

from cognite import neat
from cognite.neat import constants
from cognite.neat.core import query_generator
from cognite.neat.core import rules as rules_module
from cognite.neat.core.app import NeatApp
from cognite.neat.core.configuration import Config, configure_logging
from cognite.neat.core.loader.config import copy_examples_to_directory
from cognite.neat.core.workflow import WorkflowFullStateReport, utils
from cognite.neat.core.workflow.base import WorkflowDefinition
from cognite.neat.core.workflow.model import FlowMessage, WorkflowConfigItem
from cognite.neat.explorer.data_classes.rest import (
    DownloadFromCdfRequest,
    NodesAndEdgesRequest,
    QueryRequest,
    RuleRequest,
    RunWorkflowRequest,
    UploadToCdfRequest,
)
from cognite.neat.explorer.utils.data_mapping import rdf_result_to_api_response
from cognite.neat.explorer.utils.query_templates import query_templates
from cognite.neat.migration.wf_manifests import migrate_wf_manifest

logger = getLogger(__name__)  # temporary logger before config is loaded
config_path = Path(os.environ.get("NEAT_CONFIG_PATH", "config.yaml"))

if os.environ.get("NEAT_CDF_PROJECT"):
    logger.info("ENV NEAT_CDF_PROJECT is set, loading config from env.")
    config = Config.from_env()
elif (config_path := Path(os.environ.get("NEAT_CONFIG_PATH", "config.yaml"))).exists():
    logger.info(f"Loading config from {config_path.name}.")
    config = Config.from_yaml(config_path)
else:
    logger.error(f"Config file {config_path.name} not found.Exiting.")
    config = Config()
    config.to_yaml(config_path)

if config.load_examples:
    copy_examples_to_directory(config.data_store_path)

configure_logging(config.log_level, config.log_format)
logging.info(f" Starting NEAT version {neat.__version__}")
logging.debug(f" Config: {config.dict(exclude={'cdf_client': {'client_secret': ...}})}")

neat_app = NeatApp(config)


@asynccontextmanager
async def lifespan(app_ref: FastAPI):
    logging.info("Startup FastAPI server")
    neat_app.set_http_server(app_ref)
    neat_app.start()
    yield
    logging.info("FastApi shutdown event")
    neat_app.stop()


app = FastAPI(title="Neat", lifespan=lifespan)


origins = [
    "http://localhost:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UI cache store
cache_store = {}


counter = Counter("started_workflows", "Description of counter")

prom_app = make_asgi_app()
app.mount("/metrics", prom_app)
app.mount("/static", StaticFiles(directory=constants.UI_PATH), name="static")
app.mount("/data", StaticFiles(directory=config.data_store_path), name="data")


@app.get("/")
def read_root():
    return RedirectResponse("/static/index.html")


@app.get("/api/about")
def get_about():
    response = {"version": neat.__version__}
    installed_packages = pkg_resources.working_set
    installed_packages_list = sorted([f"{i.key}=={i.version}" for i in installed_packages])
    response["packages"] = installed_packages_list
    return response


@app.get("/api/configs/global")
def get_configs():
    return config.dict()


@app.post("/api/configs/global")
def set_configs(request: Config):
    logging.info(f"Updating global config: {request}")
    global config
    global cache_store
    global neat_app
    config = request
    config.to_yaml(config_path)
    cache_store = {}
    neat_app.stop()
    neat_app.start(config=config)
    return config


@app.get("/api/rules")
def get_rules(
    sheetname: str = "Properties",
    url: str | None = None,
    source_type: str | None = None,
    orient: str = "columns",
    workflow_name: str = "default",
    file_name: str | None = None,
    version: str | None = None,
):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    if not file_name:
        version = workflow.get_config_item("rules.version").value
        file_name = workflow.get_config_item("rules.file").value
    path = Path(config.rules_store_path, file_name)
    src = "local"
    if url:
        path = url

    if path.exists() and not version:
        logging.info(f"Loading rules from {path}")
    elif path.exists() and version:
        hash = utils.get_file_hash(path)
        if hash != version:
            neat_app.cdf_store.load_rules_file_from_cdf(file_name, version)
            src = "cdf"
    else:
        neat_app.cdf_store.load_rules_file_from_cdf(file_name, version)
        src = "cdf"

    error_text = ""
    properties = []
    classes = []
    try:
        rules = rules_module.load_rules_from_excel_file(path)
        properties = [
            {
                "class": value.class_id,
                "property": value.property_id,
                "property_description": value.description,
                "property_type": value.expected_value_type,
                "cdf_resource_type": value.cdf_resource_type,
                "cdf_metadata_type": value.resource_type_property,
                "rule_type": value.rule_type,
                "rule": value.rule,
            }
            for value in rules.properties.values()
        ]

        classes = [
            {
                "class": value.class_id,
                "class_description": value.description,
                "cdf_resource_type": value.cdf_resource_type,
                "cdf_parent_resource": value.parent_asset,
            }
            for value in rules.classes.values()
        ]
    except Exception as e:
        error_text = str(e)

    return {
        "properties": properties,
        "classes": classes,
        "file_name": path.name,
        "hash": utils.get_file_hash(path),
        "error_text": error_text,
        "src": src,
    }


@app.get("/api/list-queries")
def list_queries():
    counter.inc()
    return query_templates


def get_data_from_graph(sparq_query: str, graph_name: str = "source", workflow_name: str = "default"):
    total_elapsed_time = 0
    api_result = {"error": ""}
    result = None

    try:
        logging.info(f"Preparing query :{sparq_query} ")
        start_time = time.perf_counter()
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        try:
            if not workflow.source_graph or not workflow.solution_graph:
                workflow.step_load_transformation_rules()
                workflow.step_configuring_stores(clean_start=False)
        except Exception as e:
            logging.debug(f"Error while loading transformation rules or stores : {e}")

        if graph_name == "source":
            if workflow.source_graph:
                result = workflow.source_graph.query(sparq_query)
            else:
                logging.info("Source graph is empty , please load the graph first")
                api_result["error"] = "source graph is empty , please load the graph first"
        elif graph_name == "solution":
            if workflow.solution_graph:
                result = workflow.solution_graph.query(sparq_query)
            else:
                logging.info("Solution graph is empty , please load the graph first")
                api_result["error"] = "solution graph is empty , please load the graph first"
        else:
            raise Exception("Unknown graph name")

        stop_time = time.perf_counter()
        elapsed_time_sec_1 = stop_time - start_time
        logging.info(f"Query prepared in {elapsed_time_sec_1 * 1000} ms")

        start_time = time.perf_counter()
        if result:
            api_result = rdf_result_to_api_response(result)
        stop_time = time.perf_counter()
        elapsed_time_sec_2 = stop_time - start_time
        total_elapsed_time = elapsed_time_sec_1 + elapsed_time_sec_2
    except Exception as e:
        logging.error(f"Error while executing query :{e}")
        traceback.print_exc()
        api_result["error"] = str(e)

    api_result["query"] = sparq_query
    api_result["elapsed_time_sec"] = total_elapsed_time
    logging.info(f"Data fetched in {total_elapsed_time * 1000} ms")
    return api_result


@app.post("/api/query")
def query_graph(request: QueryRequest):
    logging.info(f"Querying graph {request.graph_name} with query {request.query}")
    sparq_query = request.query
    return get_data_from_graph(sparq_query, request.graph_name, workflow_name=request.workflow_name)


@app.post("/api/execute-rule")
def execute_rule(request: RuleRequest):
    logging.info(
        f"Executing rule type: { request.rule_type } rule : {request.rule} , workflow : {request.workflow_name} , "
        f"graph : {request.graph_name}"
    )
    # TODO : add support for other graphs
    workflow = neat_app.workflow_manager.get_workflow(request.workflow_name)
    if not workflow.source_graph or not workflow.solution_graph:
        workflow.step_load_transformation_rules()
        workflow.step_configuring_stores()
    if request.graph_name == "source":
        if not workflow.source_graph:
            logging.info("Source graph is empty , please load the graph first")
            return {"error": "source graph is empty , please load the graph first"}
        graph = workflow.source_graph
    elif request.graph_name == "solution":
        if not workflow.solution_graph:
            logging.info("Solution graph is empty , please load the graph first")
            return {"error": "solution graph is empty , please load the graph first"}
        graph = workflow.solution_graph
    else:
        raise Exception("Unknown graph name")

    if request.rule_type == "rdfpath":
        start_time = time.perf_counter()
        sparq_query = query_generator.build_sparql_query(
            graph, request.rule, prefixes=workflow.transformation_rules.prefixes
        )
    else:
        logging.error("Unknown rule type")
        return {"error": "Unknown rule type"}
    stop_time = time.perf_counter()
    elapsed_time_sec_1 = stop_time - start_time
    logging.info(f"Computed query : {sparq_query} in {elapsed_time_sec_1 * 1000} ms")

    api_result = get_data_from_graph(sparq_query, request.graph_name, workflow_name=request.workflow_name)
    api_result["elapsed_time_sec"] += elapsed_time_sec_1
    return api_result


@app.get("/api/object-properties")
def get_object_properties(reference: str, graph_name: str = "source", workflow_name: str = "default"):
    logging.info(f"Querying object-properties from {graph_name} :")
    query = f"SELECT ?property ?value WHERE {{ <{reference}> ?property ?value }} ORDER BY ?property"
    return get_data_from_graph(query, graph_name, workflow_name=workflow_name)


@app.get("/api/search")
def search(
    search_str: str, graph_name: str = "source", search_type: str = "value_exact_match", workflow_name: str = "default"
):
    logging.info(f"Search from {graph_name} :")
    if search_type == "reference":
        query = (
            f"SELECT ?class ?reference WHERE {{ {{?reference ?class <{search_str}> . }} "
            f"UNION {{ <{search_str}> ?class ?reference }} }} limit 10000"
        )

    elif search_type == "value_exact_match":
        query = (
            f"select ?object_ref ?type ?property ?value where "
            f"{{ ?object_ref ?property ?value . ?object_ref rdf:type ?type . "
            f'FILTER(?value="{search_str}") }} limit 10000'
        )
    elif search_type == "value_regexp":
        query = (
            f"select ?object_ref ?type ?property ?value where "
            f"{{ ?object_ref ?property ?value . ?object_ref rdf:type ?type .  "
            f'FILTER regex(?value, "{search_str}","i") }} limit 10000'
        )
    return get_data_from_graph(query, graph_name, workflow_name=workflow_name)


@app.get("/api/get-classes")
def get_classes(graph_name: str = "source", workflow_name: str = "default", cache: bool = True):
    logging.info(f"Querying graph classes from graph name : {graph_name}, cache : {cache}")
    cache_key = f"classes_{graph_name}"
    if cache_key in cache_store and cache:
        return cache_store[cache_key]
    query = (
        "SELECT ?class (count(?s) as ?instances ) WHERE { ?s rdf:type ?class . } "
        "group by ?class order by DESC(?instances)"
    )
    api_result = get_data_from_graph(query, graph_name, workflow_name)
    cache_store["get_classes"] = api_result
    return api_result


@app.post("/api/get-nodes-and-edges")
def get_nodes_and_edges(request: NodesAndEdgesRequest):
    logging.info("Querying graph nodes and edges :")
    if "get_nodes_and_edges" in cache_store and request.cache:
        return cache_store["get_nodes_and_edges"]
    nodes_result = {}
    edges_result = {}
    query = ""
    elapsed_time_sec = 0
    """
    "nodes": [
        {
            "node_id": "http://purl.org/nordic44#_a63ce14e-fba0-4f9e-8b59-7ef2fe887ff8",
            "node_class": "http://entsoe.eu/CIM/SchemaExtension/3/2#RateTemperature",
            "node_name": "-5degreeCelsius"
        }],
    "edges": [
        {
            "src_object_ref": "http://purl.org/nordic44#_f1769eaa-9aeb-11e5-91da-b8763fd99c5f",
            "conn": "http://iec.ch/TC57/2013/CIM-schema-cim16#OperationalLimitSet.Terminal",
            "dst_object_ref": "http://purl.org/nordic44#_2dd90186-bdfb-11e5-94fa-c8f73332c8f4"
        },
    """
    if request.sparql_query:
        mixed_result = get_data_from_graph(request.sparql_query, request.graph_name, request.workflow_name)

        edges_result = []
        nodes_result = []
        try:
            nodes_result = [
                {
                    "node_id": v[rdflib.Variable("node_id")],
                    "node_class": v[rdflib.Variable("node_class")],
                    "node_name": v[rdflib.Variable("node_name")],
                }
                for v in mixed_result["rows"]
            ]
        except Exception as e:
            logging.error(f"Error while parsing nodes : {e}")

        try:
            edges_result = [
                {
                    "src_object_ref": v[rdflib.Variable("src_object_ref")],
                    "dst_object_ref": v[rdflib.Variable("dst_object_ref")],
                }
                for v in mixed_result["rows"]
                if rdflib.Variable("src_object_ref") in v and rdflib.Variable("dst_object_ref") in v
            ]
        except Exception as e:
            logging.error(f"Error while parsing edges : {e}")

        query = request.sparql_query
        elapsed_time_sec = mixed_result["elapsed_time_sec"]
    else:
        nodes_filter = ""
        edges_dst_filter = ""
        edges_src_filter = ""

        if len(request.node_class_filter) > 0:
            nodes_filter = "VALUES ?node_class { " + " ".join([f"<{x}>" for x in request.node_class_filter]) + " }"

        node_name_property = request.node_name_property or "cim:IdentifiedObject.name"
        nodes_query = f"SELECT DISTINCT ?node_id ?node_class ?node_name WHERE \
        {{ {nodes_filter} \
        ?node_id {node_name_property} ?node_name . ?node_id rdf:type ?node_class }} "
        if len(request.src_edge_filter) > 0:
            edges_src_filter = (
                "VALUES ?src_object_class { " + " ".join([f"<{x}>" for x in request.src_edge_filter]) + " }"
            )
        if len(request.dst_edge_filter) > 0:
            edges_dst_filter = (
                "VALUES ?dst_object_class { " + " ".join([f"<{x}>" for x in request.dst_edge_filter]) + " }"
            )

        edges_query = f"SELECT  ?src_object_ref ?conn ?dst_object_ref \
            WHERE {{ \
            {edges_src_filter} \
            {edges_dst_filter} \
            ?src_object_ref ?conn  ?dst_object_ref . \
            ?src_object_ref  rdf:type ?src_object_class . \
            ?dst_object_ref  rdf:type ?dst_object_class .\
            }} "
        nodes_query = f"{nodes_query} LIMIT {request.limit}"
        edges_query = f"{edges_query} LIMIT {request.limit}"
        logging.info(f"Nodes query : {nodes_query}")
        logging.info(f"Edges query : {edges_query}")
        nodes_result = get_data_from_graph(nodes_query, request.graph_name, request.workflow_name)
        edges_result = get_data_from_graph(edges_query, request.graph_name, request.workflow_name)
        elapsed_time_sec = nodes_result["elapsed_time_sec"] + edges_result["elapsed_time_sec"]
        query = nodes_query + edges_query
        nodes_result = nodes_result["rows"]
        edges_result = edges_result["rows"]

    merged_result = {
        "nodes": nodes_result,
        "edges": edges_result,
        "error": "",
        "elapsed_time_sec": elapsed_time_sec,
        "query": query,
    }

    if request.cache:
        cache_store["get_nodes_and_edges"] = merged_result
    return merged_result


@app.post("/api/workflow/start")
def start_workflow(request: RunWorkflowRequest):
    logging.info("Starting workflow endpoint")
    start_status = neat_app.workflow_manager.start_workflow_instance(
        request.name, sync=request.sync, flow_msg=FlowMessage()
    )
    result = {"workflow_instance": None, "is_success": start_status.is_success, "status_text": start_status.status_text}
    return {"result": result}


@app.get("/api/workflow/stats/{workflow_name}", response_model=WorkflowFullStateReport)
def get_workflow_stats(
    workflow_name: str,
) -> WorkflowFullStateReport:
    logging.info("Hit the get_workflow_stats endpoint")
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    return workflow.get_state()


@app.get("/api/workflow/workflows")
def get_workflows():
    return {"workflows": neat_app.workflow_manager.get_list_of_workflows()}


@app.get("/api/workflow/executions")
def get_list_of_workflow_executions():
    return {"executions": neat_app.cdf_store.get_list_of_workflow_executions_from_cdf()}


@app.get("/api/workflow/detailed-execution-report/{execution_id}")
def get_detailed_execution(execution_id: str):
    return {"report": neat_app.cdf_store.get_detailed_workflow_execution_report_from_cdf(execution_id)}


@app.post("/api/workflow/reload-workflows")
def reload_workflows():
    neat_app.workflow_manager.load_workflows_from_storage_v2()
    neat_app.triggers_manager.reload_all_triggers()
    return {"result": "ok", "workflows": neat_app.workflow_manager.get_list_of_workflows()}


@app.get("/api/workflow/workflow-definition/{workflow_name}")
def get_workflow_definition(workflow_name: str):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    return {"definition": workflow.get_workflow_definition()}


@app.get("/api/workflow/workflow-src/{workflow_name}/{file_name}")
def get_workflow_src(workflow_name: str, file_name: str):
    src = neat_app.workflow_manager.get_workflow_src(workflow_name, file_name=file_name)
    return FileResponse(src, media_type="text/plain")


@app.post("/api/workflow/workflow-definition/{workflow_name}")
def update_workflow_definition(workflow_name: str, request: WorkflowDefinition):
    neat_app.workflow_manager.update_workflow(workflow_name, request)
    neat_app.workflow_manager.save_workflow_to_storage(workflow_name)
    return {"result": "ok"}


@app.post("/api/workflow/upload-wf-to-cdf/{workflow_name}")
def upload_workflow_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    neat_app.cdf_store.save_workflow_to_cdf(
        workflow_name, changed_by=request.author, comments=request.comments, tag=request.tag
    )
    return {"result": "ok"}


@app.post("/api/workflow/upload-rules-cdf/{workflow_name}")
def upload_rules_to_cdf(workflow_name: str, request: UploadToCdfRequest):
    file_path = Path(config.rules_store_path, request.file_name)
    neat_app.cdf_store.save_resource_to_cdf(
        workflow_name, "neat-wf-rules", file_path, changed_by=request.author, comments=request.comments
    )
    return {"result": "ok"}


@app.post("/api/workflow/download-wf-from-cdf")
def download_wf_from_cdf(request: DownloadFromCdfRequest):
    neat_app.cdf_store.load_workflows_from_cdf(request.file_name, request.version)
    return {"result": "ok"}


@app.post("/api/workflow/download-rules-from-cdf")
def download_rules_to_cdf(request: DownloadFromCdfRequest):
    neat_app.cdf_store.load_rules_file_from_cdf(request.file_name, request.version)
    return {"file_name": request.file_name, "hash": request.version}


@app.post("/api/workflow/migrate-workflow")
def migrate_workflow():
    return migrate_wf_manifest(config.data_store_path)


@app.get("/api/workflow/pre-cdf-assets/{workflow_name}")
def get_pre_cdf_assets(workflow_name: str):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"assets": []}
    return {"assets": workflow.categorized_assets}


@app.get("/api/metrics")
def get_metrics():
    metrics = REGISTRY.collect()
    return {"prom_metrics": metrics}


@app.get("/api/cdf/neat-resources")
def get_neat_resources(resource_type: str = None):
    result = neat_app.cdf_store.get_list_of_resources_from_cdf(resource_type=resource_type)
    logging.debug(f"Got {len(result)} resources")
    return {"result": result}


@app.post("/api/cdf/init-neat-resources")
def init_neat_cdf_resources(resource_type: str = None):
    neat_app.cdf_store.init_cdf_resources(resource_type=resource_type)
    return {"result": "ok"}


@app.post("/api/file/upload/{workflow_name}/{file_type}/{step_id}/{action}")
async def file_upload_handler(files: list[UploadFile], workflow_name: str, file_type: str, step_id: str, action: str):
    # get directory path
    upload_dir = config.rules_store_path
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
        file_version = utils.get_file_hash(full_path)
        break  # only one file is supported for now

    if "update_config" in action and file_type == "rules":
        logging.info("Automatically updating workflow config")
        workflow = neat_app.workflow_manager.get_workflow(workflow_name)
        workflow_defintion = workflow.get_workflow_definition()

        # update config item rules.file with the new file name
        config_item = workflow_defintion.get_config_item("rules.file")
        if config_item is None:
            config_item = WorkflowConfigItem(name="rules.file", value=file_name, label="Rules file name", group="rules")
        config_item.value = file_name
        workflow_defintion.upsert_config_item(config_item)
        # update config item rules.file with the new file name
        config_item = workflow_defintion.get_config_item("rules.version")
        if config_item is None:
            config_item = WorkflowConfigItem(name="rules.version", value="", label="Rules file version", group="rules")
            workflow_defintion.upsert_config_item(config_item)
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
