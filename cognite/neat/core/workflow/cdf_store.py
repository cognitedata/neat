import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Dict

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, FileMetadataUpdate, LabelDefinition, LabelFilter
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from cognite.neat.core.workflow.model import WorkflowFullStateReport, WorkflowState, WorkflowStepEvent
from cognite.neat.core.workflow.utils import get_file_hash


class NeatCdfResource(BaseModel):
    id: int = None
    name: str
    rtype: str
    last_updated_time: int = None
    last_updated_by: str = None
    version: str = None
    tag: str = None
    comments: str = None
    external_id: str = None
    is_latest: bool = False


class CdfStore:
    def __init__(
        self,
        client: CogniteClient,
        data_set_id: int,
        workflows_storage_path: Path = None,
        rules_storage_path: Path = None,
    ):
        self.client = client
        self.data_set_id = data_set_id
        # todo use pathlib
        self.workflows_storage_path = str(workflows_storage_path)
        self.rules_storage_path = str(rules_storage_path)
        self.workflows_storage_type = "file"

    def init_cdf_resources(self, resource_type="all"):
        if self.client and self.data_set_id:
            try:
                if resource_type == "all" or resource_type == "labels":
                    list = self.client.labels.list(external_id_prefix="neat-")
                    if len(list) == 0:
                        labels = [
                            LabelDefinition(
                                external_id="neat-workflow", name="neat-workflow", data_set_id=self.data_set_id
                            ),
                            LabelDefinition(
                                external_id="neat-latest", name="neat-latest", data_set_id=self.data_set_id
                            ),
                        ]
                        self.client.labels.create(labels)
                    else:
                        logging.debug("Labels already exists.")
            except Exception as e:
                logging.debug(f"Failed to create labels.{e}")

    def package_workflow(self, workflow_name):
        """Creates a zip archive from a folder"""
        folder_path = os.path.join(self.workflows_storage_path, workflow_name)
        archive_path = os.path.join(self.workflows_storage_path, f"{workflow_name}.zip")
        # Make sure the folder exists
        if not os.path.isdir(folder_path):
            logging.error(f"Error: {folder_path} is not a directory")
            raise Exception(f"Can't package workflow.Error: {folder_path} is not a directory")

        # Create a ZipFile object with write mode
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the directory and add each json file to the archive
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Check if the file has a .json extension
                    if (
                        file.endswith(".yaml")
                        or file.endswith(".py")
                        or file.endswith(".xlsx")
                        or file.endswith(".csv")
                        or file.endswith(".json")
                        or file.endswith(".parquet")
                    ):
                        # Add the file to the archive
                        zipf.write(file_path, os.path.relpath(file_path, folder_path))

    def extract_workflow_package(self, workflow_name: str):
        # Make sure the archive exists
        workflow_name = workflow_name.replace(".zip", "")
        package_full_path = Path(self.workflows_storage_path).joinpath(f"{workflow_name}.zip")
        output_folder = Path(self.workflows_storage_path).joinpath(workflow_name)
        if not os.path.isfile(package_full_path):
            print(f"Error: {package_full_path} is not a file")
            raise Exception(f"Can't extract workflow package. Error: {package_full_path} is not a file")

        # Remove the output folder if it already exists
        if output_folder.exists():
            shutil.rmtree(output_folder)
        # Create the output folder if it does not exist
        os.makedirs(output_folder, exist_ok=True)

        # Extract the contents of the archive to the output folder
        with zipfile.ZipFile(package_full_path, "r") as zipf:
            zipf.extractall(output_folder)

    def load_workflows_from_cfg_by_filter(self, config_filter: list[str] = None) -> str:
        """Load workflow package from CDF and extract it to the storage path"""
        # filter syntax: name:workflow_name=version; tag:tag_name
        try:
            for filter_item in config_filter:
                filter_type = filter_item.split(":")[0]
                if filter_type == "name":
                    filter_workflow_name_with_version_l = filter_item.split(":")[1].split("=")
                    filter_workflow_name = filter_workflow_name_with_version_l[0]
                    if len(filter_workflow_name_with_version_l) > 1:
                        filter_workflow_version = filter_workflow_name_with_version_l[1]
                    else:
                        filter_workflow_version = None
                    logging.info(
                        f"Loading workflow filtered by name: {filter_workflow_name} version: {filter_workflow_version}"
                    )
                    self.load_workflows_from_cdf(filter_workflow_name, filter_workflow_version)
                elif filter_type == "tag":
                    tag = filter_item.split(":")[1]
                    logging.info(f"Loading workflow filtered by tag: {tag}")
                    self.load_workflows_from_cdf(metadata_filter={"tag": tag})

        except Exception as e:
            logging.error(f"Failed to load workflows by filter. Error: {e}")

    def load_workflows_from_cdf(
        self, workflow_name: str = None, version: str = None, metadata_filter: Dict[str, str] = None
    ) -> list[str]:
        """Load workflow package or multiple workfllows from CDF and extract it to the storage path"""
        # TODO: Add workflow and tag filters
        if self.data_set_id and self.client:
            if workflow_name:
                workflow_name = workflow_name if ".zip" in workflow_name else f"{workflow_name}.zip"
            labels = ["neat-workflow"]
            meta = metadata_filter or {}
            if version:
                meta["hash"] = version
            else:
                labels.append("neat-latest")
            label_filter = LabelFilter(contains_all=labels)
            if workflow_name:
                files_metada = self.client.files.list(name=workflow_name, labels=label_filter, metadata=meta)
            elif metadata_filter:
                files_metada = self.client.files.list(labels=label_filter, metadata=meta)
            else:
                raise Exception("Workflow name or metadata_filter is required")

            files_external_ids = []
            for file_meta in files_metada:
                self.client.files.download(self.workflows_storage_path, external_id=file_meta.external_id)
                logging.info(
                    f"Workflow {file_meta.name} , external_id = {file_meta.external_id} syccessfully downloaded from CDF"
                )
                self.extract_workflow_package(file_meta.name)
                files_external_ids.append(file_meta.external_id)
            return files_external_ids
        else:
            logging.error("No CDF client or data set id provided")

    def save_workflow_to_cdf(self, name: str, tag: str = "", changed_by: str = "", comments: str = "") -> None:
        """Saves entire workflow (all artifacts) to CDF."""
        self.package_workflow(name)
        if self.data_set_id and self.client:
            zip_file = Path(self.workflows_storage_path) / f"{name}.zip"
            if zip_file.exists():
                self.save_resource_to_cdf(name, "workflow-package", zip_file, tag, changed_by, comments)
                os.remove(zip_file)
                logging.info(f"Workflow package {name} uploaded to CDF")
            else:
                logging.error(f"Workflow package {name} not found, skipping")
        else:
            logging.error("No CDF client or data set id provided")

    def save_resource_to_cdf(
        self,
        workflow_name: str,
        resource_type: str,
        file_path: Path,
        tag: str = "",
        changed_by: str = "",
        comments: str = "",
    ) -> None:
        """Saves resources to cdf. For instance workflow package, rules file, etc"""
        if self.data_set_id and self.client:
            if not os.path.exists(file_path):
                logging.error(f"File {file_path} not found, skipping")
                return
            # removing the latest tag from all files related to this workflow
            files_metada = self.client.files.list(
                name=file_path.name,
                metadata={
                    "workflow_name": workflow_name,
                    "resource_type": resource_type,
                },
            )
            for file_meta in files_metada:
                meta_update = FileMetadataUpdate(id=file_meta.id).labels.remove("neat-latest")
                self.client.files.update(meta_update)

            hash_ = get_file_hash(file_path)
            self.client.files.upload(
                file_path,
                name=file_path.name,
                external_id=f"neat-wf-{hash_}",
                labels=["neat-workflow", "neat-latest"],
                metadata={
                    "tag": tag,
                    "hash": hash_,
                    "workflow_name": workflow_name,
                    "resource_type": resource_type,
                    "changed_by": changed_by,
                    "comments": comments,
                },
                source="neat",
                overwrite=True,
                data_set_id=self.data_set_id,
            )
        else:
            logging.error("No CDF client or data set id provided")

    def load_rules_file_from_cdf(self, name: str, version: str = None):
        logging.info(f"Loading rules file {name} (version = {version} ) from CDF ")
        # TODO: Download latest if version is not specified
        files_metadata = self.client.files.list(name=name, metadata={"hash": version})
        if len(files_metadata) > 0:
            self.client.files.download(self.rules_storage_path, external_id=files_metadata[0].external_id)
        else:
            raise Exception(f"Rules file {name} with version {version} not found in CDF")

    def get_list_of_resources_from_cdf(self, resource_type: str) -> list[NeatCdfResource]:
        logging.info(f"Getting list of resources of type {resource_type} from CDF")
        label_filter = LabelFilter(contains_any=["neat-workflow"])
        files_metadata = self.client.files.list(labels=label_filter, metadata={"resource_type": resource_type})

        return [
            NeatCdfResource(
                id=file_meta.id,
                name=file_meta.name,
                external_id=file_meta.external_id,
                version=file_meta.metadata["hash"],
                rtype=file_meta.metadata["resource_type"],
                comments=file_meta.metadata["comments"],
                last_updated_by=file_meta.metadata["changed_by"],
                tag=file_meta.metadata["tag"],
                last_updated_time=file_meta.last_updated_time,
            )
            for file_meta in files_metadata
        ]

    def get_list_of_workflow_executions_from_cdf(self, limit=200) -> list[WorkflowFullStateReport]:
        """Returns list of workflow executions from CDF."""
        logging.debug("Getting list of workflow executions from CDF")
        events = self.client.events.list(type="neat-workflow-run", source="neat", sort=["startTime:desc"], limit=limit)
        executions = []
        for event in events:
            if (time.time() - event.start_time > 24 * 60 * 60) and event.subtype == "RUNNING":
                event.subtype = "EXPIRED"

            try:
                executions.append(
                    WorkflowFullStateReport(
                        run_id=event.metadata["run_id"],
                        elapsed_time=float(event.metadata["elapsed_time"]) if "elapsed_time" in event.metadata else 0,
                        last_error=event.metadata["error"] if "error" in event.metadata else "",
                        execution_log=[],
                        workflow_name=event.metadata["workflow_name"] if "workflow_name" in event.metadata else "",
                        last_updated_time=event.last_updated_time,
                        start_time=event.start_time,
                        end_time=event.end_time,
                        state=event.subtype,
                    )
                )
            except Exception as e:
                logging.info(
                    f"Failed to parse workflow execution event for workflow , run_id = {event.metadata['run_id']}, error = {e}"
                )
        return executions

    def get_detailed_workflow_execution_report_from_cdf(self, run_id: str) -> WorkflowFullStateReport:
        """Returns detailed workflow execution report from CDF"""
        logging.debug(f"Getting detailed workflow execution {run_id} from CDF")
        external_id = f"neat-wf-run-{run_id}"
        event = self.client.events.retrieve(external_id=external_id)
        steps_log = []
        if event:
            try:
                if "execution_log" in event.metadata:
                    steps_log = json.loads(event.metadata["execution_log"])
                else:
                    external_id = f"neat-wf-execution-log-{run_id}"
                    steps_log = self.client.files.download_bytes(external_id=external_id)
            except Exception as e:
                logging.info(
                    f"Failed to parse execution log for workflow {event.metadata['workflow_name']}, run_id = {event.metadata['run_id']}, error = {e}"
                )
                steps_log = []
            return WorkflowFullStateReport(
                run_id=event.metadata["run_id"],
                elapsed_time=float(event.metadata["elapsed_time"]) if "elapsed_time" in event.metadata else 0,
                last_error=event.metadata["error"] if "error" in event.metadata else "",
                execution_log=steps_log,
                workflow_name=event.metadata["workflow_name"] if "workflow_name" in event.metadata else "",
                last_updated_time=event.last_updated_time,
                start_time=event.start_time,
                end_time=event.end_time,
                state=event.subtype,
            )
        raise Exception(f"Workflow execution with run_id = {run_id} not found")

    def report_workflow_execution_to_cdf(self, report: WorkflowFullStateReport):
        # Report workflow run to CDF as single event with all the steps attached either in metadata or attached file (depends on the size)
        metadata = {
            "run_id": report.run_id,
            "elapsed_time": report.elapsed_time,
            "error": report.last_error,
            "execution_log": "",
            "workflow_name": report.workflow_name,
        }
        external_id = f"neat-wf-run-{report.run_id}"
        # serialized_execution_log = json.dumps([step.dict() for step in report.execution_log])
        serialized_execution_log = json.dumps(jsonable_encoder(report.execution_log))
        execution_log_size = bytes(serialized_execution_log, "utf-8").__sizeof__()
        logging.debug(f"Serialized execution log size: {execution_log_size}")
        # logging.debug(f"Serialized execution log: {serialized_execution_log}")

        if report.start_time:
            report.start_time = report.start_time * 1000
        if report.end_time:
            report.end_time = report.end_time * 1000

        event = Event(
            external_id=external_id,
            type="neat-workflow-run",
            subtype=report.state,
            start_time=report.start_time,
            end_time=report.end_time,
            source="neat",
            metadata=metadata,
            data_set_id=self.data_set_id,
        )

        if execution_log_size > 128000:  # 128K limit for Event metadata
            self.client.files.upload_bytes(
                serialized_execution_log,
                name="neat-workflow-execution-log.json",
                external_id=f"neat-wf-execution-log-{report.run_id}",
                metadata={"run_id": report.run_id, "workflow_name": report.workflow_name},
                source="neat",
                overwrite=True,
                data_set_id=self.data_set_id,
            )
        elif serialized_execution_log:
            event.metadata["execution_log"] = serialized_execution_log

        if report.state in [WorkflowState.CREATED, WorkflowState.RUNNING]:
            res = self.client.events.create(event)
        elif report.state in [WorkflowState.COMPLETED, WorkflowState.FAILED]:
            res = self.client.events.update(event)
        else:
            logging.error(f"Unknown workflow state {report.state}")
            return

        if res.external_id == external_id:
            logging.debug(f"Workflow run {report.run_id} reported to CDF")
        else:
            logging.error(f"Workflow run {report.run_id} not reported to CDF due to error: {res}")

    def report_step_event_to_cdf(self, event: WorkflowStepEvent):
        pass
