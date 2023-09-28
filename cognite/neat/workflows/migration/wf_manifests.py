import logging
import os
from pathlib import Path

import yaml


def migrate_wf_manifest(wf_store_path: Path):
    """Migrate workflow manifests . Changed name of element from groups -> system_components"""
    migrated_files = []
    wf_store_path = wf_store_path / "workflows"
    for wf_module_name in os.listdir(wf_store_path):
        wf_module_full_path = wf_store_path / wf_module_name

        if wf_module_full_path.is_dir():
            metadata_file = wf_store_path / wf_module_name / "workflow.yaml"
            metadata_file_migrated = wf_store_path / wf_module_name / "workflow.yaml"
            logging.info(f"Loading workflow {wf_module_name} metadata from {metadata_file}")
            if metadata_file.exists():
                with metadata_file.open() as f:
                    manifest_yaml = yaml.safe_load(f)
                    logging.info(f"Loaded workflow {wf_module_name} metadata from {metadata_file}")
                if "groups" in manifest_yaml:
                    logging.info(f"Found groups in {metadata_file}, migrating to system_components")
                    manifest_yaml["system_components"] = manifest_yaml["groups"]
                    del manifest_yaml["groups"]
                    with metadata_file_migrated.open("w") as f:
                        yaml.dump(manifest_yaml, f, indent=4)
                        migrated_files.append(metadata_file_migrated)
            else:
                logging.info(f"Metadata file {metadata_file} not found, skipping")
                continue
    return migrated_files
