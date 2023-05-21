
import json
import os
from pathlib import Path
import logging


def migrate_wf_manifest(wf_store_path: Path):
    for wf_module_name in os.listdir(wf_store_path):
        wf_module_full_path = wf_store_path / wf_module_name
        if wf_module_full_path.is_dir():
            metadata_file = wf_store_path / wf_module_name / "workflow.yaml"
            logging.info(f"Loading workflow {wf_module_name} metadata from {metadata_file}")
            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    manifest_json = json.load(f)
                    if "groups" in manifest_json:
                        manifest_json["system_components"] = manifest_json["groups"]
                        del manifest_json["groups"]
                        json.dump(manifest_json, f, indent=2)
                    
    return