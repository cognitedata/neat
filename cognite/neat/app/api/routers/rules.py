import logging
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from rdflib import Namespace

from cognite.neat.app.api.configuration import neat_app
from cognite.neat.rules.models import Class, Metadata, Property, TransformationRules
from cognite.neat.rules.parser import parse_rules_from_excel_file
from cognite.neat.workflows.utils import get_file_hash

router = APIRouter()


@router.get("/api/rules")
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
    workflow_defintion = workflow.get_workflow_definition()

    if not file_name:
        for step in workflow_defintion.steps:
            if step.method == "LoadTransformationRules":
                file_name = step.configs["file_name"]
                version = step.configs["version"]

    path = Path(neat_app.config.rules_store_path, file_name)
    src = "local"
    if url:
        path = url

    if path.exists() and not version:
        logging.info(f"Loading rules from {path}")
    elif path.exists() and version:
        hash = get_file_hash(path)
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
        rules = parse_rules_from_excel_file(path)
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
        "hash": get_file_hash(path),
        "error_text": error_text,
        "src": src,
    }


@router.get("/api/rules/from_file")
def get_original_rules_from_file(
    file_name: str | None = None,
):
    path = Path(neat_app.config.rules_store_path, file_name)
    rules = parse_rules_from_excel_file(path)
    return Response(content=rules.model_dump_json(), media_type="application/json")


@router.get("/api/rules/from_workflow")
def get_original_rules_from_workflow(
    workflow_name: str,
):
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    context = workflow.get_context()
    rules = context["RulesData"].rules
    return Response(content=rules.model_dump_json(), media_type="application/json")


@router.post("/api/rules/model_and_transformations")
def post_original_rules(request: dict):
    # MyModel(**json.loads(…))
    request["metadata"]["namespace"] = Namespace(request["metadata"]["namespace"])
    metadata = Metadata(**request["metadata"])
    classes: dict[str:Class] = {}
    for class_, val in request["classes"].items():
        classes[class_] = Class(**val)
    properties: dict[str:Property] = {}    
    
    for prop, val in request["properties"].items():
        val["resource_type_property"] = []
        properties[prop] = Property(**val)

    prefixes: dict[str, Namespace] = {}
    for prefix, val in request["prefixes"].items():
        prefixes[prefix] = Namespace(val)

    rules = TransformationRules(metadata=metadata, classes=classes, properties=properties, prefixes=prefixes, instances=[])

    return {"status": "ok", "metadata": metadata.description, "classes": len(rules.classes)}
