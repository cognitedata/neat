import base64
import time
from pathlib import Path
from typing import ClassVar

import requests
from cognite.client import CogniteClient

from cognite.neat._issues.errors import WorkflowStepNotInitializedError
from cognite.neat._workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat._workflows.steps.step_model import Configurable, Step

CATEGORY = "IO Steps"


__all__ = [
    "DownloadFileFromGitHub",
    "UploadFileToGitHub",
    "DownloadFileFromCDF",
    "UploadFileToCDF",
    "DownloadDataFromRestApiToFile",
]


class DownloadFileFromGitHub(Step):
    """
    This step fetches and stores the file from private Github repository
    """

    description = "This step fetches and stores the file from private Github repository"
    category = CATEGORY
    version = "private-beta"
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
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)
        github_filepath = self.configs["github.filepath"]
        github_personal_token = self.configs["github.personal_token"]
        github_owner = self.configs["github.owner"]
        github_repo = self.configs["github.repo"]
        github_branch = self.configs["github.branch"]
        github_file_name = Path(github_filepath).name
        local_file_name = self.configs["local.file_name"] or github_file_name
        full_local_file_path = self.data_store_path / Path(self.configs["local.storage_dir"])

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
            f'<a href="/data/{local_download_path}?{time.time()}" '
            f'target="_blank">{local_file_name}</a>'
        )

        return FlowMessage(output_text=output_text)


class UploadFileToGitHub(Step):
    """
    This step uploads file to private Github repository
    """

    description = "This step uploads file to private Github repository"
    category = CATEGORY
    version = "private-beta"
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
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)
        github_filepath = self.configs["github.filepath"]
        github_personal_token = self.configs["github.personal_token"]
        github_owner = self.configs["github.owner"]
        github_repo = self.configs["github.repo"]
        github_branch = self.configs["github.branch"]
        local_file_name = self.configs["local.file_name"]
        full_local_file_path = self.data_store_path / Path(self.configs["local.storage_dir"]) / local_file_name

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
    category = CATEGORY
    version = "private-beta"
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
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)

        output_dir = self.data_store_path / Path(self.configs["local.storage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        full_local_file_path = output_dir / self.configs["local.file_name"]
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
    category = CATEGORY
    version = "private-beta"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="cdf.external_id", value="", label="Exernal Id for the file to be stored in CDF"),
        Configurable(
            name="cdf.dataset_id", value="", label="Dataset Id for the file to be stored in CDF. Must be a number"
        ),
        Configurable(name="local.file_name", value="", label="The name of the local file to be uploaded to CDF"),
        Configurable(name="local.storage_dir", value="rules/", label="Local directory where the file is stored"),
    ]

    def run(self, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)
        full_local_file_path = (
            self.data_store_path / Path(self.configs["local.storage_dir"]) / self.configs["local.file_name"]
        )
        dataset_id = int(self.configs["cdf.dataset_id"]) if self.configs["cdf.dataset_id"].isdigit() else None
        cdf_client.files.upload(
            str(full_local_file_path),
            external_id=self.configs["cdf.external_id"],
            overwrite=True,
            data_set_id=dataset_id,
        )
        return FlowMessage(output_text=f"File {self.configs['local.file_name']} uploaded to CDF successfully")


class DownloadDataFromRestApiToFile(Step):
    """
    This step downloads the response from a REST API and saves it to a file.
    """

    description = "This step downloads the response from a REST API and saves it to a file."
    category = CATEGORY
    version = "private-beta"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="api_url",
            value="",
            label="API URL",
        ),
        Configurable(
            name="output_file_path",
            value="workflows/workflow_name/output.json",
            label="Output File Path. The path must be relative to the data store path.",
        ),
        Configurable(
            name="http_method",
            value="GET",
            label="HTTP Method (GET/POST/PUT)",
            options=["GET", "POST", "PUT"],
        ),
        Configurable(
            name="auth_mode",
            value="none",
            label="Authentication Mode (basic/token/none)",
            options=["basic", "token", "none"],
        ),
        Configurable(
            name="username",
            value="",
            label="Username (for basic auth)",
        ),
        Configurable(
            name="password",
            value="",
            label="Password (for basic auth)",
            type="password",
        ),
        Configurable(
            name="token",
            value="",
            label="Token (for token auth)",
            type="password",
        ),
        Configurable(
            name="response_destination",
            value="file",
            label="Destination for the response (file/flow_message/both)",
            options=["file", "flow_message", "both"],
        ),
        Configurable(
            name="http_headers",
            value="",
            label="Custom HTTP headers separated by ';' . Example: \
              'Content-Type: application/json; Accept: application/json'",
        ),
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        api_url = self.configs["api_url"]
        output_file_path = Path(self.data_store_path) / Path(self.configs["output_file_path"])

        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        http_method = self.configs["http_method"].upper()
        auth_mode = self.configs["auth_mode"]
        username = self.configs["username"]
        password = self.configs["password"]
        token = self.configs["token"]
        http_headers_str = self.configs.get("http_headers", "")
        headers = {}
        for header in http_headers_str.split(";"):
            if header:
                key, value = header.split(":")
                headers[key.strip()] = value.strip()
        try:
            if auth_mode == "basic":
                if username and password:
                    headers["Authorization"] = f'Basic {base64.b64encode(f"{username}:{password}".encode()).decode()}'
                else:
                    return FlowMessage(
                        error_text="Username and password are required for Basic Authentication",
                        step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
                    )
            elif auth_mode == "token":
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    return FlowMessage(
                        error_text="Token is required for Token Authentication",
                        step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
                    )

            if http_method not in ("GET", "POST", "PUT"):
                return FlowMessage(
                    error_text="Unsupported HTTP method. Supported methods are GET, POST, and PUT.",
                    step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
                )

            if http_method == "GET":
                response = requests.get(api_url, headers=headers, stream=True)
            elif http_method == "POST":
                response = requests.post(api_url, headers=headers, stream=True)
            elif http_method == "PUT":
                response = requests.put(api_url, headers=headers, stream=True)

            if response.status_code >= 200 and response.status_code < 300:
                payload = None
                if self.configs["response_destination"] in ("flow_message", "both"):
                    payload = response.json()
                    with output_file_path.open("wb") as output_file:
                        output_file.write(response.content)
                else:
                    with output_file_path.open("wb") as output_file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                output_file.write(chunk)

                return FlowMessage(output_text="Response downloaded and saved successfully.", payload=payload)
            else:
                return FlowMessage(
                    error_text=f"Failed to fetch response. Status Code: {response.status_code}",
                    step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
                )
        except Exception as e:
            return FlowMessage(
                error_text=f"An error occurred: {e!s}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )
