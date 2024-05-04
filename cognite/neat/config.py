import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, Field
from yaml import safe_load

from cognite.neat.constants import EXAMPLE_GRAPHS, EXAMPLE_RULES, EXAMPLE_WORKFLOWS
from cognite.neat.utils.cdf import InteractiveCogniteClient, ServiceCogniteClient

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


class Config(BaseModel):
    workflows_store_type: WorkflowsStoreType = WorkflowsStoreType.FILE
    data_store_path: Path = Field(default_factory=lambda: Path.cwd() / "data")

    workflow_downloader_filter: list[str] | None = Field(
        description="List of workflow names+tags to filter on when downloading workflows from CDF. "
        "Example name:workflow_name=version,tag:tag_name",
        default=None,
    )

    cdf_client: InteractiveCogniteClient | ServiceCogniteClient = ServiceCogniteClient()
    cdf_default_dataset_id: int = 0
    load_examples: bool = True

    log_level: Literal["ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_format: str = LOG_FORMAT
    download_workflows_from_cdf: bool = Field(
        default=False, description="Downloads all workflows from CDF automatically and stores them locally"
    )

    stop_on_error: bool = False

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
        dump = json.loads(self.json())

        with filepath.open("w") as f:
            yaml.safe_dump(dump, f)

    @classmethod
    def from_env(cls) -> Self:
        missing = "Missing"
        cdf_config = ServiceCogniteClient(
            project=os.environ.get("NEAT_CDF_PROJECT", missing),
            client_id=os.environ.get("NEAT_CDF_CLIENT_ID", missing),
            client_secret=os.environ.get("NEAT_CDF_CLIENT_SECRET", missing),
            base_url=os.environ.get("NEAT_CDF_BASE_URL", missing),
            token_url=os.environ.get("NEAT_CDF_TOKEN_URL", missing),
            scopes=[os.environ.get("NEAT_CDF_SCOPES", missing)],
            timeout=int(os.environ.get("NEAT_CDF_CLIENT_TIMEOUT", "60")),
            max_workers=int(os.environ.get("NEAT_CDF_CLIENT_MAX_WORKERS", "3")),
        )

        if workflow_downloader_filter_value := os.environ.get("NEAT_WORKFLOW_DOWNLOADER_FILTER", None):
            workflow_downloader_filter = workflow_downloader_filter_value.split(",")
        else:
            workflow_downloader_filter = None

        return cls(
            cdf_client=cdf_config,
            workflows_store_type=os.environ.get(  # type: ignore[arg-type]
                "NEAT_WORKFLOWS_STORE_TYPE", WorkflowsStoreType.FILE
            ),
            data_store_path=Path(os.environ.get("NEAT_DATA_PATH", "/app/data")),
            cdf_default_dataset_id=int(os.environ.get("NEAT_CDF_DEFAULT_DATASET_ID", 6476640149881990)),
            log_level=cast(Literal["ERROR", "WARNING", "INFO", "DEBUG"], os.environ.get("NEAT_LOG_LEVEL", "INFO")),
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
