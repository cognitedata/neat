import logging
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Response
from rdflib import Namespace

from cognite.neat.app.api.configuration import NEAT_APP
from cognite.neat.app.api.data_classes.rest import TransformationRulesUpdateRequest
from cognite.neat.legacy.rules import exporters as legacy_exporters
from cognite.neat.legacy.rules import importers as legacy_importers
from cognite.neat.legacy.rules.models._base import EntityTypes
from cognite.neat.legacy.rules.models.rules import Class, Classes, Metadata, Properties, Property, Rules
from cognite.neat.rules import importers
from cognite.neat.rules.models import RoleTypes
from cognite.neat.workflows.steps.data_contracts import RulesData
from cognite.neat.workflows.steps.lib.current.rules_exporter import RulesToExcel
from cognite.neat.workflows.steps.lib.current.rules_importer import ExcelToRules
from cognite.neat.workflows.steps.lib.legacy.rules_importer import ImportExcelToRules
from cognite.neat.workflows.utils import get_file_hash

router = APIRouter()


@router.get("/api/rules/list")
def get_rules_list():
    rules_dir = Path(NEAT_APP.config.rules_store_path)
    return {"result": [str(file.name) for file in rules_dir.glob("*.xlsx")]}


@router.get("/api/rules")
def get_rules(
    sheetname: str = "Properties",
    url: str | None = None,
    source_type: str | None = None,
    orient: str = "columns",
    workflow_name: str = "default",
    file_name: str | None = None,
    version: str | None = None,
    as_role: str | None = None,
) -> dict[str, Any]:
    rules_schema_version = ""
    if NEAT_APP.cdf_store is None or NEAT_APP.workflow_manager is None:
        return {"error": "NeatApp is not initialized"}
    if workflow_name != "undefined":
        workflow = NEAT_APP.workflow_manager.get_workflow(workflow_name)
        if workflow is None:
            return {"error": f"Workflow {workflow_name} is not found"}
        workflow_definition = workflow.get_workflow_definition()
        if not file_name:
            for step in workflow_definition.steps:
                if step.method == ImportExcelToRules.__name__:
                    file_name = step.configs["file_name"]
                    version = step.configs["version"]
                    break
                if step.method == RulesToExcel.__name__ or step.method == ExcelToRules.__name__:
                    rules_schema_version = "v2"
                    as_role = step.configs.get("as_role", "")
                    file_name = step.configs.get("File name", "")
                    if file_name:
                        break
                    file_name = step.configs.get("File path", "")
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
    remaped_rules = {}
    try:
        # Trying to load rules V1
        if rules_schema_version == "" or rules_schema_version == "v1":
            rules = cast(
                Rules, legacy_importers.ExcelImporter(path).to_rules(return_report=False, skip_validation=False)
            )
            properties = [
                {
                    "class": value.class_id,
                    "property": value.property_id,
                    "property_description": value.description,
                    "property_type": (
                        value.expected_value_type.versioned_id
                        if value.property_type == EntityTypes.object_property
                        else value.expected_value_type.suffix
                    ),
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
                }
                for value in rules.classes.values()
            ]
            rules_schema_version = "v1"
            remaped_rules = {"properties": properties, "metadata": rules.metadata.model_dump(), "classes": classes}
    except Exception as e:
        error_text = str(e)

    if rules_schema_version == "" or rules_schema_version == "v2":
        try:
            role = RoleTypes(as_role) if as_role else None
            rules_v2, issues = importers.ExcelImporter(path).to_rules(role=role)
            error_text = ""
            rules_schema_version = "v2"
            if rules_v2:
                remaped_rules = rules_v2.model_dump()
        except Exception as e:
            error_text = str(e)
            rules_schema_version = "unknown"

    return {
        "rules": remaped_rules,
        "file_name": path.name,
        "hash": get_file_hash(path),
        "error_text": error_text,
        "src": src,
        "rules_schema_version": rules_schema_version,
    }


@router.get("/api/rules/from_file")
def get_original_rules_from_file(file_name: str):
    # """Endpoint for retrieving raw transformation from file"""
    path = Path(NEAT_APP.config.rules_store_path) / file_name
    rules = cast(
        Rules, legacy_importers.ExcelImporter(filepath=path).to_rules(return_report=False, skip_validation=False)
    )
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

        legacy_exporters.ExcelExporter(rules=rules).export_to_file(path)
    return {"status": "ok"}
