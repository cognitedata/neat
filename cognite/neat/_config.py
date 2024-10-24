import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, Field, model_validator
from yaml import safe_load

from cognite.neat._constants import EXAMPLE_GRAPHS, EXAMPLE_RULES, EXAMPLE_WORKFLOWS
from cognite.neat._utils.auth import EnvironmentVariables

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RulesStoreType(StrEnum):
    """Rules Store type"""

    CDF = "cdf"
    FILE = "file"
    URL = "url"
    GOOGLE_SHEET = "google_sheet"


class WorkflowsStoreType(StrEnum):
    """Workflows Store type"""

    CDF = "cdf"
    FILE = "file"
    URL = "url"


class Config(BaseModel, arbitrary_types_allowed=True):
    workflows_store_type: WorkflowsStoreType = WorkflowsStoreType.FILE
    data_store_path: Path = Field(default_factory=lambda: Path.cwd() / "data")

    workflow_downloader_filter: list[str] | None = Field(
        description="List of workflow names+tags to filter on when downloading workflows from CDF. "
        "Example name:workflow_name=version,tag:tag_name",
        default=None,
    )

    cdf_auth_config: EnvironmentVariables = Field(default_factory=EnvironmentVariables.default)
    cdf_default_dataset_id: int = 0
    load_examples: bool = True

    log_level: Literal["ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_format: str = LOG_FORMAT
    download_workflows_from_cdf: bool = Field(
        default=False,
        description="Downloads all workflows from CDF automatically and stores them locally",
    )
    stop_on_error: bool = False

    @model_validator(mode="before")
    def backwards_compatible(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if "cdf_client" in data:
            cdf_client = data["cdf_client"]
            if isinstance(cdf_client, dict):
                if "base_url" in cdf_client:
                    base_url = cdf_client["base_url"]
                    cluster = base_url.removeprefix("https://").removesuffix(".cognitedata.com")
                else:
                    base_url, cluster = "Missing", "Missing"
                if "scopes" in cdf_client:
                    scopes = cdf_client["scopes"]
                    if isinstance(scopes, list):
                        scopes = ",".join(scopes)
                else:
                    scopes = "Missing"
                data["cdf_auth_config"] = EnvironmentVariables(
                    CDF_PROJECT=cdf_client.get("project", "Missing"),
                    CDF_CLUSTER=cluster,
                    CDF_URL=base_url,
                    IDP_CLIENT_ID=cdf_client.get("client_id", "Missing"),
                    IDP_CLIENT_SECRET=cdf_client.get("client_secret", "Missing"),
                    IDP_TOKEN_URL=cdf_client.get("token_url", "Missing"),
                    IDP_SCOPES=scopes,
                    CDF_TIMEOUT=int(cdf_client.get("timeout", 60)),
                    CDF_MAX_WORKERS=int(cdf_client.get("max_workers", 3)),
                )
        return data

    def as_legacy_config(
        self,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {}

        config["workflows_store_type"] = self.workflows_store_type
        config["data_store_path"] = str(self.data_store_path)
        config["workflows_downloader_filter"] = self.workflow_downloader_filter

        config["cdf_client"] = {}
        if self.cdf_auth_config.CDF_PROJECT not in {"Missing", "NOT SET"}:
            config["cdf_client"]["project"] = self.cdf_auth_config.CDF_PROJECT
        if self.cdf_auth_config.CDF_CLUSTER not in {"Missing", "NOT SET"}:
            config["cdf_client"]["cluster"] = self.cdf_auth_config.CDF_CLUSTER
        if self.cdf_auth_config.CDF_URL:
            config["cdf_client"]["base_url"] = self.cdf_auth_config.CDF_URL
        if self.cdf_auth_config.IDP_CLIENT_ID:
            config["cdf_client"]["client_id"] = self.cdf_auth_config.IDP_CLIENT_ID
        if self.cdf_auth_config.IDP_CLIENT_SECRET:
            config["cdf_client"]["client_secret"] = self.cdf_auth_config.IDP_CLIENT_SECRET
        if self.cdf_auth_config.IDP_TOKEN_URL:
            config["cdf_client"]["token_url"] = self.cdf_auth_config.IDP_TOKEN_URL
        if self.cdf_auth_config.IDP_SCOPES:
            config["cdf_client"]["scopes"] = self.cdf_auth_config.idp_scopes
        if self.cdf_auth_config.CDF_TIMEOUT:
            config["cdf_client"]["timeout"] = self.cdf_auth_config.CDF_TIMEOUT
        if self.cdf_auth_config.CDF_MAX_WORKERS:
            config["cdf_client"]["max_workers"] = self.cdf_auth_config.CDF_MAX_WORKERS

        config["cdf_default_dataset_id"] = self.cdf_default_dataset_id
        config["load_examples"] = self.load_examples
        config["log_level"] = self.log_level
        config["log_format"] = self.log_format
        config["download_workflows_from_cdf"] = self.download_workflows_from_cdf
        config["stop_on_error"] = self.stop_on_error

        return config

    @property
    def _dir_suffix(self) -> str:
        is_test_running = "pytest" in sys.modules
        if is_test_running:
            # Todo change the below to f"-{os.getpid()}" when all tests supports parallel execution.
            return ""
        return ""

    @property
    def rules_store_path(self) -> Path:
        return self.data_store_path / f"rules{self._dir_suffix}"

    @property
    def workflows_store_path(self) -> Path:
        return self.data_store_path / f"workflows{self._dir_suffix}"

    @property
    def source_graph_path(self) -> Path:
        return self.data_store_path / f"source-graphs{self._dir_suffix}"

    @property
    def staging_path(self) -> Path:
        return self.data_store_path / f"staging{self._dir_suffix}"

    @classmethod
    def from_yaml(cls, filepath: Path) -> Self:
        return cls(**safe_load(filepath.read_text()))

    def to_yaml(self, filepath: Path):
        # Parse as json to avoid Path and Enum objects
        dump = json.loads(self.model_dump_json())

        with filepath.open("w") as f:
            yaml.safe_dump(dump, f)

    @classmethod
    def from_env(cls) -> Self:
        missing = "Missing"
        # This is to be backwards compatible with the old config

        base_url: str | None = None
        if "NEAT_CDF_BASE_URL" in os.environ:
            base_url = os.environ["NEAT_CDF_BASE_URL"]
        if isinstance(base_url, str):
            cluster = base_url.removeprefix("https://").removesuffix(".cognitedata.com")
        else:
            cluster = missing
        variables = EnvironmentVariables(
            CDF_PROJECT=os.environ.get("NEAT_CDF_PROJECT", missing),
            CDF_CLUSTER=cluster,
            CDF_URL=base_url,
            IDP_CLIENT_ID=os.environ.get("NEAT_CDF_CLIENT_ID"),
            IDP_CLIENT_SECRET=os.environ.get("NEAT_CDF_CLIENT_SECRET"),
            IDP_TOKEN_URL=os.environ.get("NEAT_CDF_TOKEN_URL"),
            IDP_SCOPES=os.environ.get("NEAT_CDF_SCOPES"),
            CDF_TIMEOUT=int(os.environ["NEAT_CDF_CLIENT_TIMEOUT"] if "NEAT_CDF_CLIENT_TIMEOUT" in os.environ else 60),
            CDF_MAX_WORKERS=int(
                os.environ["NEAT_CDF_CLIENT_MAX_WORKERS"] if "NEAT_CDF_CLIENT_MAX_WORKERS" in os.environ else 3
            ),
        )

        if workflow_downloader_filter_value := os.environ.get("NEAT_WORKFLOW_DOWNLOADER_FILTER", None):
            workflow_downloader_filter = workflow_downloader_filter_value.split(",")
        else:
            workflow_downloader_filter = None

        return cls(
            cdf_auth_config=variables,
            workflows_store_type=os.environ.get(  # type: ignore[arg-type]
                "NEAT_WORKFLOWS_STORE_TYPE", WorkflowsStoreType.FILE
            ),
            data_store_path=Path(os.environ.get("NEAT_DATA_PATH", "_app/data")),
            cdf_default_dataset_id=int(os.environ.get("NEAT_CDF_DEFAULT_DATASET_ID", 6476640149881990)),
            log_level=cast(
                Literal["ERROR", "WARNING", "INFO", "DEBUG"],
                os.environ.get("NEAT_LOG_LEVEL", "INFO"),
            ),
            workflow_downloader_filter=workflow_downloader_filter,
            load_examples=bool(os.environ.get("NEAT_LOAD_EXAMPLES", True) in ["True", "true", "1"]),
        )


def copy_examples_to_directory(config: Config):
    """
    Copier over all the examples to the target_data_directory,
    without overwriting

    Args:
        target_data_dir : The target directory
        suffix : The suffix to add to the directory names

    """

    print(f"Copying examples into {config.data_store_path}")
    _copy_examples(EXAMPLE_RULES, config.rules_store_path)
    _copy_examples(EXAMPLE_GRAPHS, config.source_graph_path)
    _copy_examples(EXAMPLE_WORKFLOWS, config.workflows_store_path)
    config.staging_path.mkdir(exist_ok=True, parents=True)


def create_data_dir_structure(config: Config) -> None:
    """
    Create the data directory structure in empty directory

    Args:
        target_data_dir : The target directory
        suffix : The suffix to add to the directory names

    """
    for path in (
        config.rules_store_path,
        config.source_graph_path,
        config.staging_path,
        config.workflows_store_path,
    ):
        path.mkdir(exist_ok=True, parents=True)


def _copy_examples(source_dir: Path, target_dir: Path):
    for current in source_dir.rglob("*"):
        if current.is_dir():
            continue
        relative = current.relative_to(source_dir)
        if not (target := target_dir / relative).exists():
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(current, target)


def configure_logging(level: str = "DEBUG", log_format: str = LOG_FORMAT):
    """Configure logging based on config."""
    logging.basicConfig(format=log_format, level=logging.getLevelName(level), datefmt=LOG_DATE_FORMAT)
