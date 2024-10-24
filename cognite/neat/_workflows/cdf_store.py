import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, FileMetadataUpdate
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from cognite.neat._issues.errors import WorkflowConfigurationNotSetError
from cognite.neat._workflows.model import WorkflowFullStateReport, WorkflowState, WorkflowStepEvent
from cognite.neat._workflows.utils import get_file_hash


class NeatCdfResource(BaseModel):
    id: int | None = None
    name: str | None
    rtype: str
    last_updated_time: int | None = None
    last_updated_by: str | None = None
    version: str | None = None
    tag: str | None = None
    comments: str | None = None
    external_id: str | None = None
    is_latest: bool = False


class CdfStore:
    def __init__(
        self,
        client: CogniteClient,
        data_set_id: int,
        workflows_storage_path: Path | None = None,
        rules_storage_path: Path | None = None,
    ):
        self.client = client
        self.data_set_id = data_set_id
        self.workflows_storage_path = workflows_storage_path
        self.rules_storage_path = rules_storage_path
        self.workflows_storage_type = "file"

    def init_cdf_resources(self, resource_type="all"):
        if self.client and self.data_set_id:
            try:
                logging.info("Nothing to initialize")
            except Exception as e:
                logging.debug(f"Failed to create labels.{e}")

    def package_workflow(self, workflow_name: str) -> str:
        """Creates a zip archive from a folder"""
        if self.workflows_storage_path is None:
            raise WorkflowConfigurationNotSetError("workflows_storage_path")
        folder_path = self.workflows_storage_path / workflow_name
        archive_path = self.workflows_storage_path / f"{workflow_name}.zip"
        # Make sure the folder exists
        if not folder_path.is_dir():
            logging.error(f"Error: {folder_path} is not a directory")
            raise Exception(f"Can't package workflow.Error: {folder_path} is not a directory")

        # Create a ZipFile object with write mode
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the directory and add each json file to the archive
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = Path(root) / Path(file)
                    # Check if the file has a .json extension
                    if not (file.endswith(".pyc") and file.endswith(".DS_Store")):
                        # Add the file to the archive
                        zipf.write(file_path, os.path.relpath(file_path, folder_path))
        return f"{workflow_name}.zip"

    def extract_workflow_package(self, workflow_name: str):
        # Make sure the archive exists
        workflow_name = workflow_name.replace(".zip", "")
        if self.workflows_storage_path is None:
            raise WorkflowConfigurationNotSetError("workflows_storage_path")
        package_full_path = Path(self.workflows_storage_path) / f"{workflow_name}.zip"
        output_folder = Path(self.workflows_storage_path) / workflow_name
        if not package_full_path.is_file():
            print(f"Error: {package_full_path} is not a file")
            raise Exception(f"Can't extract workflow package. Error: {package_full_path} is not a file")

        # Remove the output folder if it already exists
        if output_folder.exists():
            shutil.rmtree(output_folder)
        # Create the output folder if it does not exist
        output_folder.mkdir(parents=True, exist_ok=True)

        # Extract the contents of the archive to the output folder
        with zipfile.ZipFile(package_full_path, "r") as zipf:
            zipf.extractall(output_folder)

    def load_workflows_from_cfg_by_filter(self, config_filter: list[str] | None = None) -> None:
        """Load workflow package from CDF and extract it to the storage path"""
        # filter syntax: name:workflow_name=version; tag:tag_name
        try:
            for filter_item in config_filter or []:
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
        self,
        workflow_name: str | None = None,
        version: str | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[str]:
        """Load workflow package or multiple workfllows from CDF and extract it to the storage path"""
        # TODO: Add workflow and tag filters
        if self.data_set_id and self.client:
            if workflow_name:
                workflow_name = workflow_name if ".zip" in workflow_name else f"{workflow_name}.zip"
            meta = metadata_filter or {}
            if version:
                meta["hash"] = version
            else:
                meta["is_latest"] = "true"
            if workflow_name:
                files_metada = self.client.files.list(source="neat", name=workflow_name, metadata=meta)
            elif metadata_filter:
                files_metada = self.client.files.list(source="neat", metadata=meta)
            else:
                raise Exception("Workflow name or metadata_filter is required")

            files_external_ids: list[str] = []
            if self.workflows_storage_path is None:
                raise Exception("Workflow storage path is not defined")
            for file_meta in files_metada:
                self.client.files.download(self.workflows_storage_path, external_id=file_meta.external_id)
                logging.info(
                    f"Workflow {file_meta.name} , "
                    f"external_id = {file_meta.external_id} syccessfully downloaded from CDF"
                )
                self.extract_workflow_package(file_meta.name or "Unknown Workflow")
                if file_meta.external_id:
                    files_external_ids.append(file_meta.external_id)
            return files_external_ids
        else:
            logging.error("No CDF client or data set id provided")
            return []

    def save_workflow_to_cdf(self, name: str, tag: str = "", changed_by: str = "", comments: str = "") -> None:
        """Saves entire workflow (all artifacts) to CDF."""
        self.package_workflow(name)
        if self.data_set_id and self.client and self.workflows_storage_path:
            zip_file = Path(self.workflows_storage_path) / f"{name}.zip"
            if zip_file.exists():
                self.save_resource_to_cdf(name, "workflow-package", zip_file, tag, changed_by, comments)
                zip_file.unlink()
                logging.info(f"Workflow package {name} uploaded to CDF")
            else:
                logging.error(f"Workflow package {name} not found, skipping")
        else:
            logging.error("No CDF client, data set id or workflow_storage_path provided")

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
            if not file_path.exists():
                logging.error(f"File {file_path} not found, skipping")
                return
            # removing the latest tag from all files related to this workflow
            files_metada = self.client.files.list(
                name=file_path.name,
                source="neat",
                metadata={"workflow_name": workflow_name, "resource_type": resource_type, "is_latest": "true"},
            )
            for file_meta in files_metada:
                files_meta_metadata = file_meta.metadata or {}
                files_meta_metadata["is_latest"] = "false"
                meta_update = FileMetadataUpdate(id=file_meta.id).metadata.set(files_meta_metadata)
                self.client.files.update(meta_update)

            hash_ = get_file_hash(file_path)
            self.client.files.upload(
                str(file_path),
                name=file_path.name,
                external_id=f"neat-wf-{hash_}",
                metadata={
                    "tag": tag,
                    "hash": hash_,
                    "workflow_name": workflow_name,
                    "resource_type": resource_type,
                    "changed_by": changed_by,
                    "comments": comments,
                    "is_latest": "true",
                },
                source="neat",
                overwrite=True,
                data_set_id=self.data_set_id,
            )
        else:
            logging.error("No CDF client or data set id provided")

    def load_rules_file_from_cdf(self, name: str, version: str | None = None):
        logging.info(f"Loading rules file {name} (version = {version} ) from CDF ")
        if version:
            metadata = {"hash": str(version)}
        else:
            metadata = {"is_latest": "true"}
        files_metadata = self.client.files.list(name=name, source="neat", metadata=metadata)
        if len(files_metadata) > 0 and self.rules_storage_path:
            self.client.files.download(self.rules_storage_path, external_id=files_metadata[0].external_id)
        else:
            raise Exception(f"Rules file {name} with version {version} not found in CDF")

    def get_list_of_resources_from_cdf(self, resource_type: str) -> list[NeatCdfResource]:
        logging.info(f"Getting list of resources of type {resource_type} from CDF")
        if not self.data_set_id:
            return []

        files_metadata = self.client.files.list(source="neat", metadata={"resource_type": resource_type})

        output: list[NeatCdfResource] = []
        for file_meta in files_metadata:
            if file_meta.metadata:
                is_latest = file_meta.metadata.get("is_latest", "false") == "true"
            else:
                is_latest = False

            metadata = file_meta.metadata or {}
            neat_cdf_resource = NeatCdfResource(
                id=file_meta.id,
                name=file_meta.name,
                external_id=file_meta.external_id,
                version=metadata["hash"],
                rtype=metadata["resource_type"],
                comments=metadata["comments"],
                last_updated_by=metadata["changed_by"],
                tag=metadata["tag"],
                last_updated_time=file_meta.last_updated_time,
                is_latest=is_latest,
            )
            output.append(neat_cdf_resource)
        return output

    def get_list_of_workflow_executions_from_cdf(self, limit=70) -> list[WorkflowFullStateReport]:
        """Returns list of workflow executions from CDF."""
        logging.debug("Getting list of workflow executions from CDF")
        if not self.data_set_id:
            return []
        events = self.client.events.list(type="neat-workflow-run", source="neat", sort=["startTime:desc"], limit=limit)
        executions = []
        for event in events:
            if (time.time() - (event.start_time or 0) > 24 * 60 * 60) and event.subtype == "RUNNING":
                event.subtype = "EXPIRED"
            metadata = event.metadata or {}
            try:
                executions.append(
                    WorkflowFullStateReport(
                        run_id=metadata["run_id"],
                        elapsed_time=float(metadata["elapsed_time"]) if "elapsed_time" in metadata else 0,
                        last_error=metadata["error"] if "error" in metadata else "",
                        execution_log=[],
                        workflow_name=metadata["workflow_name"] if "workflow_name" in metadata else "",
                        last_updated_time=event.last_updated_time,
                        start_time=event.start_time,
                        end_time=event.end_time,
                        state=WorkflowState((event.subtype or WorkflowState.UNKNOWN).upper()),
                    )
                )
            except Exception as e:
                logging.info(
                    f"Failed to parse workflow execution event for workflow, "
                    f"run_id = {metadata['run_id']}, error = {e}"
                )
        return executions

    def get_detailed_workflow_execution_report_from_cdf(self, run_id: str) -> WorkflowFullStateReport | None:
        """Returns detailed workflow execution report from CDF"""
        logging.debug(f"Getting detailed workflow execution {run_id} from CDF")
        external_id = f"neat-wf-run-{run_id}"
        if not self.data_set_id:
            return None
        event = self.client.events.retrieve(external_id=external_id)
        if event:
            metadata = event.metadata or {}
            try:
                if "execution_log" in metadata:
                    steps_log = json.loads(metadata["execution_log"])
                else:
                    external_id = f"neat-wf-execution-log-{run_id}"
                    steps_log = self.client.files.download_bytes(external_id=external_id)
            except Exception as e:
                logging.info(
                    f"Failed to parse execution log for workflow {metadata['workflow_name']}, "
                    f"run_id = {metadata['run_id']}, error = {e}"
                )
                steps_log = []

            metadata = event.metadata or {}
            return WorkflowFullStateReport(
                run_id=metadata["run_id"],
                elapsed_time=float(metadata["elapsed_time"]) if "elapsed_time" in metadata else 0,
                last_error=metadata["error"] if "error" in metadata else "",
                execution_log=steps_log,
                workflow_name=metadata["workflow_name"] if "workflow_name" in metadata else "",
                last_updated_time=event.last_updated_time,
                start_time=event.start_time,
                end_time=event.end_time,
                state=WorkflowState((event.subtype or WorkflowState.UNKNOWN).upper()),
            )
        raise Exception(f"Workflow execution with run_id = {run_id} not found")

    def report_workflow_execution_to_cdf(self, report: WorkflowFullStateReport):
        # Report workflow run to CDF as single event with all the steps attached either in metadata
        # or attached file (depends on the size)
        if not self.data_set_id:
            return
        metadata: dict[str, str] = {
            "run_id": str(report.run_id),
            "elapsed_time": str(report.elapsed_time),
            "error": str(report.last_error),
            "execution_log": "",
            "workflow_name": str(report.workflow_name),
        }
        external_id = f"neat-wf-run-{report.run_id}"
        serialized_execution_log = json.dumps(jsonable_encoder(report.execution_log))
        execution_log_size = bytes(serialized_execution_log, "utf-8").__sizeof__()
        logging.debug(f"Serialized execution log size: {execution_log_size}")

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
                metadata={"run_id": str(report.run_id), "workflow_name": str(report.workflow_name)},
                source="neat",
                overwrite=True,
                data_set_id=self.data_set_id,
            )
        elif serialized_execution_log:
            event.metadata["execution_log"] = serialized_execution_log  # type: ignore[index]

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
