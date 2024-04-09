import json
import shutil
import tempfile
from pathlib import Path
from typing import cast

from fastapi import APIRouter, UploadFile

from cognite.neat.rules import importers
from cognite.neat.rules.models._rules.base import RoleTypes

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
        rules, issues = importers.OWLImporter(owl_filepath=temp_filepath).to_rules(role=RoleTypes.dms_architect)

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
