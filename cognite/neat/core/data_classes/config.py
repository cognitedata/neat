import json
import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Literal, Optional, Self

import yaml
from pydantic import BaseModel, Field, validator
from yaml import safe_load

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "DEBUG", log_format: str = LOG_FORMAT):
    """Configure logging based on config."""
    logging.basicConfig(format=log_format, level=logging.getLevelName(level), datefmt=LOG_DATE_FORMAT)


class RdfStoreType(StrEnum):
    """RDF Store type"""

    MEMORY = "memory"
    FILE = "file"
    GRAPHDB = "graphdb"
    SPARQL = "sparql"
    OXIGRAPH = "oxigraph"


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


class ClientConfig(BaseModel):
    project: str = "dev"
    client_id: str = "neat"
    client_name: str = "neat"
    base_url: str = "https://api.cognitedata.com"
    scopes: list[str] = ["project:read", "project:write"]
    timeout: int = 60
    max_workers: int = 3

    @validator("scopes", pre=True)
    def string_to_list(cls, value):
        return [value] if isinstance(value, str) else value


class InteractiveClient(ClientConfig):
    authority_url: str
    redirect_port: int = 53_000


class ServiceClient(ClientConfig):
    token_url: str = "https://login.microsoftonline.com/common/oauth2/token"
    client_secret: str = "secret"


class RdfStoreConfig(BaseModel):
    type: RdfStoreType
    file_path: str = None
    query_url: str = None
    update_url: str = None
    user: str = None
    password: str = None
    api_root_url: str = "http://localhost:7200"


class Config(BaseModel):
    workflows_store_type: RulesStoreType = WorkflowsStoreType.FILE
    data_store_path: Path = Field(default_factory=lambda: Path.cwd() / "data")

    workflow_downloader_filter: Optional[list[str]] = Field(
        description="List of workflow names+tags to filter on when downloading workflows from CDF. "
        "Example name:workflow_name=version,tag:tag_name",
        default=None,
    )

    cdf_client: InteractiveClient | ServiceClient = ServiceClient()
    cdf_default_dataset_id: int = 0
    load_examples: bool = True

    log_level: Literal["ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_format: str = LOG_FORMAT
    download_workflows_from_cdf: bool = Field(
        default=False, description="Downloads all workflows from CDF automatically and stores them locally"
    )

    stop_on_error: bool = False

    @property
    def rules_store_path(self) -> Path:
        return self.data_store_path / "rules"

    @property
    def workflows_store_path(self) -> Path:
        return self.data_store_path / "workflows"

    @property
    def source_graph_path(self) -> Path:
        return self.data_store_path / "source_graphs"

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
        cdf_config = ServiceClient(
            project=os.environ.get("NEAT_CDF_PROJECT"),
            client_name=os.environ.get("NEAT_CDF_CLIENT_NAME"),
            client_id=os.environ.get("NEAT_CDF_CLIENT_ID"),
            client_secret=os.environ.get("NEAT_CDF_CLIENT_SECRET"),
            base_url=os.environ.get("NEAT_CDF_BASE_URL"),
            token_url=os.environ.get("NEAT_CDF_TOKEN_URL"),
            scopes=[os.environ.get("NEAT_CDF_SCOPES")],
            timeout=int(os.environ.get("NEAT_CDF_CLIENT_TIMEOUT", "60")),
            max_workers=int(os.environ.get("NEAT_CDF_CLIENT_MAX_WORKERS", "3")),
        )

        if workflow_downloader_filter := os.environ.get("NEAT_WORKFLOW_DOWNLOADER_FILTER", None):
            workflow_downloader_filter = workflow_downloader_filter.split(",")

        return cls(
            cdf_client=cdf_config,
            workflows_store_type=os.environ.get("NEAT_WORKFLOWS_STORE_TYPE", WorkflowsStoreType.FILE),
            workflows_store_path=os.environ.get("NEAT_DATA_PATH", "/app/data"),
            cdf_default_dataset_id=os.environ.get("NEAT_CDF_DEFAULT_DATASET_ID", 6476640149881990),
            log_level=os.environ.get("NEAT_LOG_LEVEL", "INFO"),
            workflow_downloader_filter=workflow_downloader_filter,
            load_examples=bool(os.environ.get("NEAT_LOAD_EXAMPLES", True)),
        )


EXCLUDE_PATHS = [
    "root['labels']",
    "root['metadata']['create_time']",
    "root['metadata']['start_time']",
    "root['metadata']['update_time']",
    "root['metadata']['end_time']",
    "root['metadata']['resurrection_time']",  # need to account for assets that are brought back to life
]
