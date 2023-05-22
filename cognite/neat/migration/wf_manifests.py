
import os
from pathlib import Path
import logging

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
                with open(metadata_file, "r") as f:
                    # metadata_str = f.read()
                    manifest_yaml = yaml.load(f, Loader=yaml.Loader)
                    logging.info(f"Loaded workflow {wf_module_name} metadata from {metadata_file}")
                if "groups" in manifest_yaml:
                    logging.info(f"Found groups in {metadata_file}, migrating to system_components")
                    manifest_yaml["system_components"] = manifest_yaml["groups"]
                    del manifest_yaml["groups"]
                    with open(metadata_file_migrated, "w") as f:
                        yaml.dump(manifest_yaml, f, indent=4)
                        migrated_files.append(metadata_file_migrated)
            else:
                logging.info(f"Metadata file {metadata_file} not found, skipping")
                continue            
    return migrated_files