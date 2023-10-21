import logging
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Response
from rdflib import Namespace

from cognite.neat.app.api.configuration import NEAT_APP
from cognite.neat.app.api.data_classes.rest import TransformationRulesUpdateRequest
from cognite.neat.rules import exporter, importer
from cognite.neat.rules.models.rules import Class, Classes, Metadata, Properties, Property, Rules
from cognite.neat.workflows.steps.data_contracts import RulesData
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
) -> dict[str, Any]:
    if NEAT_APP.cdf_store is None or NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"error": f"Workflow {workflow_name} is not found"}
    workflow_defintion = workflow.get_workflow_definition()

    if not file_name:
        for step in workflow_defintion.steps:
            if step.method == "LoadTransformationRules":
                file_name = step.configs["file_name"]
                version = step.configs["version"]
                break
    if not file_name:
        return {"error": "File name is not provided"}
    rules_file = Path(file_name)
    if str(rules_file.parent) == ".":
        path = Path(NEAT_APP.config.rules_store_path) / rules_file
    else:
        path = Path(NEAT_APP.config.data_store_path) / rules_file

    src = "local"
    if url:
        path = Path(url)

    if path.exists() and not version:
        logging.info(f"Loading rules from {path}")
    elif path.exists() and version:
        hash_ = get_file_hash(path)
        if hash_ != version:
            NEAT_APP.cdf_store.load_rules_file_from_cdf(file_name, version)
            src = "cdf"
    else:
        NEAT_APP.cdf_store.load_rules_file_from_cdf(file_name, version)
        src = "cdf"

    error_text = ""
    properties = []
    classes = []
    try:
        rules = cast(Rules, importer.ExcelImporter(path).to_rules(return_report=False, skip_validation=False))

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
def get_original_rules_from_file(file_name: str):
    # """Endpoint for retrieving raw transformation from file"""
    path = Path(NEAT_APP.config.rules_store_path) / file_name
    rules = cast(Rules, importer.ExcelImporter(filepath=path).to_rules(return_report=False, skip_validation=False))
    return Response(content=rules.model_dump_json(), media_type="application/json")


@router.get("/api/rules/from_workflow")
def get_original_rules_from_workflow(workflow_name: str):
    """Endpoing for retrieving transformation from memmory"""
    workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
    if workflow is None:
        return {"error": f"Workflow {workflow_name} is not found"}
    context = workflow.get_context()
    rules_data = context["RulesData"]
    if type(rules_data) != RulesData:
        return {"error": "RulesData is not found in workflow context"}

    return Response(content=rules_data.rules.model_dump_json(), media_type="application/json")


@router.post("/api/rules/model_and_transformations")
def upsert_rules(request: TransformationRulesUpdateRequest):
    """Endpoing for updating transformation rules via API . This endpoint is still experimental"""
    rules = request.rules_object
    rules["metadata"]["namespace"] = Namespace(rules["metadata"]["namespace"])
    metadata = Metadata(**rules["metadata"])
    classes = Classes()
    for class_, val in rules["classes"].items():
        classes[class_] = Class(**val)
    properties = Properties()

    for prop, val in rules["properties"].items():
        val["resource_type_property"] = []
        properties[prop] = Property(**val)

    prefixes: dict[str, Namespace] = {}
    for prefix, val in rules["prefixes"].items():
        prefixes[prefix] = Namespace(val)

    rules = Rules(metadata=metadata, classes=classes, properties=properties, prefixes=prefixes, instances=[])
    if request.output_format == "excel":
        rules_file = Path(request.file_name)
        if str(rules_file.parent) == ".":
            path = Path(NEAT_APP.config.rules_store_path) / rules_file
        else:
            path = Path(NEAT_APP.config.data_store_path) / rules_file

        exporter.ExcelExporter(rules=rules, filepath=path).export()
    return {"status": "ok"}
