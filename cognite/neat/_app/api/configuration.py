import logging
import os
from pathlib import Path
from typing import Any

from cognite.client import CogniteClient
from fastapi import FastAPI

from cognite import neat
from cognite.neat._config import Config, configure_logging, copy_examples_to_directory, create_data_dir_structure
from cognite.neat._constants import PACKAGE_DIRECTORY
from cognite.neat._workflows.cdf_store import CdfStore
from cognite.neat._workflows.manager import WorkflowManager
from cognite.neat._workflows.triggers import TriggerManager

UI_PATH = PACKAGE_DIRECTORY / "_app" / "ui" / "neat-app" / "build"


class NeatApp:
    def __init__(self, config: Config, cdf_client: CogniteClient | None = None):
        self.config = config
        self.cdf_client: CogniteClient | None = None
        self.cdf_store: CdfStore | None = None
        self.fast_api_app: FastAPI | None = None
        self.cdf_client = cdf_client

    def set_http_server(self, fast_api_app: FastAPI):
        """Set the http server to be used by the triggers manager"""
        self.fast_api_app = fast_api_app

    def start(self, config: Config | None = None):
        logging.info("Starting NeatApp")
        if config:
            self.config = config
        logging.info("Initializing global objects")
        if not self.cdf_client:
            self.cdf_client = self.config.cdf_auth_config.get_client()
        self.cdf_store = CdfStore(
            self.cdf_client,
            self.config.cdf_default_dataset_id,
            workflows_storage_path=self.config.workflows_store_path,
            rules_storage_path=self.config.rules_store_path,
        )

        # Automatically downloading workflows from CDF if enabled in config
        if self.config.workflow_downloader_filter:
            self.cdf_store.load_workflows_from_cfg_by_filter(self.config.workflow_downloader_filter)

        self.workflow_manager = WorkflowManager(
            client=self.cdf_client,
            config=self.config,
        )
        self.workflow_manager.load_workflows_from_storage()
        self.triggers_manager = TriggerManager(workflow_manager=self.workflow_manager)
        self.triggers_manager.start_time_schedulers()
        logging.info("NeatApp started")

    def stop(self):
        logging.info("Stopping NeatApp")
        if self.triggers_manager:
            self.triggers_manager.stop_scheduler_main_loop()
        self.cdf_client = None
        self.cdf_store = None
        self.workflow_manager = None
        self.triggers_manager = None
        logging.info("NeatApp stopped")


def create_neat_app() -> NeatApp:
    logger = logging.getLogger(__name__)  # temporary logger before config is loaded

    if os.environ.get("NEAT_CDF_PROJECT"):
        logger.info("ENV NEAT_CDF_PROJECT is set, loading config from env.")
        config = Config.from_env()
    elif (config_path := Path(os.environ.get("NEAT_CONFIG_PATH", "config.yaml"))).exists():
        logger.info(f"Loading config from {config_path.name}.")
        config = Config.from_yaml(config_path)
    else:
        logger.error(f"Config file {config_path.name} not found.Exiting.")
        config = Config()
        config.to_yaml(config_path)

    if config.load_examples:
        copy_examples_to_directory(config)
    else:
        create_data_dir_structure(config)

    configure_logging(config.log_level, config.log_format)
    logging.info(f" Starting NEAT version {neat.__version__}")
    logging.debug(
        f" Config: {config.model_dump(exclude={'cdf_client': {'client_secret': ...}})}"  # type: ignore[arg-type]
    )

    return NeatApp(config)


NEAT_APP = create_neat_app()
CACHE_STORE: dict[str, Any] = {}
