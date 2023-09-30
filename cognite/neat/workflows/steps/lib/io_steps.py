import base64
import time
from pathlib import Path
from typing import ClassVar

import requests
from cognite.client import CogniteClient

from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["DownloadFileFromGitHub", "UploadFileToGitHub", "DownloadFileFromCDF", "UploadFileToCDF"]


class DownloadFileFromGitHub(Step):
    """
    This step fetches and stores the file from private Github repository
    """

    description = "This step fetches and stores the file from private Github repository"
    category = "Input/Output"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="github.filepath", value="", label="File path to the file stored on Github"),
        Configurable(
            name="github.personal_token",
            value="",
            label="Github Personal Access Token which allows fetching file from private Github repository",
            type="password",
        ),
        Configurable(name="github.owner", value="", label="Github repository owner, also know as github organization"),
        Configurable(name="github.repo", value="", label="Github repository from which the file is being fetched"),
        Configurable(
            name="github.branch", value="main", label="Github repository branch from which the file is being fetched"
        ),
        Configurable(
            name="local.file_name", value="", label="The name of the file under which it will be stored locally"
        ),
        Configurable(name="local.storage_dir", value="rules/", label="The directory where the file will be stored"),
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        github_filepath = self.configs["github.filepath"]
        github_personal_token = self.configs["github.personal_token"]
        github_owner = self.configs["github.owner"]
        github_repo = self.configs["github.repo"]
        github_branch = self.configs["github.branch"]
        github_file_name = Path(github_filepath).name
        local_file_name = self.configs["local.file_name"] or github_file_name
        full_local_file_path = Path(self.data_store_path) / Path(self.configs["local.storage_dir"])

        if not full_local_file_path.exists():
            full_local_file_path.mkdir(parents=True, exist_ok=True)

        r = requests.get(
            f"https://api.github.com/repos/{github_owner}/{github_repo }"
            + f"/contents/{github_filepath}?ref={github_branch}",
            headers={"accept": "application/vnd.github.v3.raw", "authorization": f"token {github_personal_token}"},
        )

        if r.status_code >= 200 and r.status_code < 300:
            local_download_path = Path(self.configs["local.storage_dir"]) / local_file_name
            full_local_file_path = full_local_file_path / local_file_name
            try:
                with full_local_file_path.open("wb") as f:
                    f.write(r.content)
            except Exception as e:
                return FlowMessage(
                    error_text=f"Error writing file to {full_local_file_path}. Error: {e}",
                    step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
                )
        else:
            return FlowMessage(
                error_text=f"Error fetching file from Github: {r.text}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        output_text = (
            "<p></p>"
            f" Downloaded file <b>{github_file_name}</b> from:"
            f'<p><a href="https://github.com/{github_owner}/{github_repo}/tree/{github_branch}"'
            f'target="_blank">https://github.com/{github_owner}/{github_repo}/tree/{github_branch}</a></p>'
        )

        output_text += (
            "<p></p>"
            " Downloaded rules accessible locally under file name "
            f'<a href="http://localhost:8000/data/{local_download_path}?{time.time()}" '
            f'target="_blank">{local_file_name}</a>'
        )

        return FlowMessage(output_text=output_text)


class UploadFileToGitHub(Step):
    """
    This step uploads file to private Github repository
    """

    description = "This step uploads file to private Github repository"
    category = "Input/Output"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="github.filepath", value="", label="File path to the file stored on Github"),
        Configurable(
            name="github.personal_token",
            value="",
            label="Github Personal Access Token which allows uploading file to private Github repository",
            type="password",
        ),
        Configurable(name="github.owner", value="", label="Github repository owner, also know as github organization"),
        Configurable(name="github.repo", value="", label="Github repository the file is being uploaded to"),
        Configurable(
            name="github.branch", value="main", label="Github repository branch the file is being uploaded to"
        ),
        Configurable(
            name="github.commit_message",
            value="New file",
            label="The commit message to be used when uploading the file",
        ),
        Configurable(name="local.file_name", value="", label="The name of the local file to be uploaded to Github"),
        Configurable(name="local.storage_dir", value="rules/", label="Local directory where the file is stored"),
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)
        github_filepath = self.configs["github.filepath"]
        github_personal_token = self.configs["github.personal_token"]
        github_owner = self.configs["github.owner"]
        github_repo = self.configs["github.repo"]
        github_branch = self.configs["github.branch"]
        local_file_name = self.configs["local.file_name"]
        full_local_file_path = Path(self.data_store_path) / Path(self.configs["local.storage_dir"]) / local_file_name

        if not full_local_file_path.exists():
            return FlowMessage(
                error_text=f"File {full_local_file_path} doesn't exist",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        with full_local_file_path.open("rb") as f:
            file_content = f.read()

        headers = {"Authorization": f"Bearer {github_personal_token}", "Content-Type": "application/json"}

        # Create a content object
        content = {
            "message": self.configs["github.commit_message"],
            "content": base64.b64encode(file_content).decode("utf-8"),
            "branch": github_branch,
        }
        base_url = f"https://api.github.com/repos/{github_owner}/{github_repo }/contents/{github_filepath}"

        # Check if the file exists already
        response = requests.get(f"{base_url}?ref={github_branch}", headers=headers)

        if response.status_code == 200:
            # File exists, update it
            sha = response.json()["sha"]
            content["sha"] = sha
            response = requests.put(base_url, headers=headers, json=content)
        elif response.status_code == 404:
            # File doesn't exist, create it
            response = requests.put(base_url, headers=headers, json=content)
        else:
            # Unexpected response
            return FlowMessage(
                error_text=f"Unexpected response from Github: {response.text}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )
        if response.status_code == 200 or response.status_code == 201:
            return FlowMessage(output_text=f"File {local_file_name} uploaded to Github successfully")
        else:
            return FlowMessage(
                error_text=f"Error uploading file to Github: {response.text}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )


class DownloadFileFromCDF(Step):
    """
    This step fetches and stores file from CDF
    """

    description = "This step fetches and stores file from CDF"
    category = "Input/Output"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="cdf.external_id", value="", label="External ID of the file stored in CDF"),
        Configurable(
            name="local.file_name",
            value="",
            label="The name of the file under which the content will be stored locally",
        ),
        Configurable(name="local.storage_dir", value="rules/", label="The directory where the file will be stored"),
    ]

    def run(self, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        full_local_file_path = (
            Path(self.data_store_path) / Path(self.configs["local.storage_dir"]) / self.configs["local.file_name"]
        )
        cdf_client.files.download_to_path(full_local_file_path, external_id=self.configs["cdf.external_id"])
        if full_local_file_path.exists():
            return FlowMessage(output_text=f"File {self.configs['local.file_name']} downloaded from CDF successfully")
        else:
            return FlowMessage(
                error_text="Error downloading file from CDF", step_execution_status=StepExecutionStatus.ABORT_AND_FAIL
            )


class UploadFileToCDF(Step):
    """
    This step uploads file to CDF
    """

    description = "This step uploads file to CDF"
    category = "Input/Output"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="cdf.external_id", value="", label="Exernal Id for the file to be stored in CDF"),
        Configurable(
            name="cdf.dataset_id", value="", label="Dataset Id for the file to be stored in CDF. Must be a number"
        ),
        Configurable(name="local.file_name", value="", label="The name of the local file to be uploaded to CDF"),
        Configurable(name="local.storage_dir", value="rules/", label="Local directory where the file is stored"),
    ]

    def run(self, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)
        full_local_file_path = (
            Path(self.data_store_path) / Path(self.configs["local.storage_dir"]) / self.configs["local.file_name"]
        )
        dataset_id = int(self.configs["cdf.dataset_id"]) if self.configs["cdf.dataset_id"].isdigit() else None
        cdf_client.files.upload(
            full_local_file_path, external_id=self.configs["cdf.external_id"], overwrite=True, data_set_id=dataset_id
        )
        return FlowMessage(output_text=f"File {self.configs['local.file_name']} uploaded to CDF successfully")
