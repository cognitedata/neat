import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import cast

from fastapi import APIRouter, UploadFile

from cognite.neat.app.api.configuration import NEAT_APP
from cognite.neat.rules import exporters, importers
from cognite.neat.rules.models import DMSRules, RoleTypes

router = APIRouter()


@router.post("/api/core/convert")
async def convert_data_model_to_rules(file: UploadFile):
    suffix = Path(cast(str, file.filename)).suffix

    if suffix not in [".xlsx", ".ttl", ".owl", ".json", ".yaml"]:
        return {
            "filename": None,
            "content": None,
            "issues": [f"File type {suffix} not supported. Supported types are ['.xlsx', '.ttl', '.json', '.yaml']"],
        }

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        shutil.copyfileobj(file.file, temp)  # type: ignore # known issue with mypy
        temp_filepath = Path(temp.name)

    # read as Excel rules
    if suffix == ".xlsx":
        rules, issues = importers.ExcelImporter(filepath=temp_filepath).to_rules(role=RoleTypes.dms_architect)

    # load as OWL
    elif suffix in [".ttl", ".owl"]:
        rules, issues = importers.OWLImporter(filepath=temp_filepath).to_rules(role=RoleTypes.dms_architect)

    # load as YAML
    elif suffix in [".yml", ".yaml"]:
        rules, issues = importers.YAMLImporter.from_file(temp_filepath).to_rules(role=RoleTypes.dms_architect)

    # load as JSON
    elif suffix == ".json":
        with temp_filepath.open() as temp:
            json_data = json.load(temp)
        rules, issues = importers.YAMLImporter(raw_data=json.loads(json_data)).to_rules(role=RoleTypes.dms_architect)

    # Remove the temporary file
    temp_filepath.unlink()

    return {"filename": file.filename, "content": rules.model_dump(by_alias=True) if rules else None, "issues": issues}


@router.post("/api/core/rules2dms")
async def convert_rules_to_dms(rules: DMSRules):
    dms_schema = exporters.DMSExporter().export(rules)
    containers = {f"{container.space}:{container.external_id}": container.dump() for container in dms_schema.containers}
    views = {f"{view.space}:{view.external_id}": view.dump() for view in dms_schema.views}

    if views and containers:
        _to_visualization_compliant_views(views, containers)

    return {
        "views": list(views.values()) if views else None,
        "containers": list(containers.values()) if containers else None,
    }


def _to_visualization_compliant_views(views, containers):
    for view in views.values():
        for property in view["properties"].values():
            # needs coping information from container:
            if property.get("container", None) and property["container"]["type"] == "container":
                container_id = f"{property['container']['space']}:{property['container']['externalId']}"
                container_property_def = deepcopy(
                    containers[container_id]["properties"][property["containerPropertyIdentifier"]]
                )
                property["type"] = container_property_def["type"]
                container_property_def.pop("type")
                property.update(container_property_def)


@router.post("/api/core/publish-rules")
async def publish_rules_as_data_model(rules: DMSRules):
    if NEAT_APP.cdf_client:
        uploaded = exporters.DMSExporter().export_to_cdf(rules, NEAT_APP.cdf_client)
        return {"uploaded": uploaded}
    else:
        return {"uploaded": []}
