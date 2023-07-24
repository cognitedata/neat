import logging

from cognite.client import CogniteClient
from fastapi import FastAPI

from cognite.neat.app.api.configuration import Config
from cognite.neat.core.utils.utils import get_cognite_client_from_config
from cognite.neat.workflows.workflow import CdfStore
from cognite.neat.workflows.workflow import WorkflowManager
from cognite.neat.workflows.workflow import TriggerManager


class NeatApp:
    def __init__(self, config: Config, cdf_client: CogniteClient = None):
        self.config = config
        self.cdf_client: CogniteClient = None
        self.cdf_store: CdfStore = None
        self.workflow_manager: WorkflowManager = None
        self.triggers_manager: TriggerManager = None
        self.fast_api_app: FastAPI = None
        self.cdf_client = cdf_client

    def set_http_server(self, fast_api_app: FastAPI):
        """Set the http server to be used by the triggers manager"""
        self.fast_api_app = fast_api_app

    def start(self, config: Config = None):
        logging.info("Starting NeatApp")
        if config:
            self.config = config
        logging.info("Initializing global objects")
        if not self.cdf_client:
            self.cdf_client = get_cognite_client_from_config(self.config.cdf_client)
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
            registry_storage_type=self.config.workflows_store_type,
            workflows_storage_path=self.config.workflows_store_path,
            rules_storage_path=self.config.rules_store_path,
            data_store_path=self.config.data_store_path,
            data_set_id=self.config.cdf_default_dataset_id,
        )
        self.workflow_manager.load_workflows_from_storage_v2()
        self.triggers_manager = TriggerManager(workflow_manager=self.workflow_manager)
        if self.fast_api_app:
            self.triggers_manager.start_http_listeners(self.fast_api_app)
        self.triggers_manager.start_time_schedulers()
        logging.info("NeatApp started")

    def stop(self):
        logging.info("Stopping NeatApp")
        self.triggers_manager.stop_scheduler_main_loop()
        self.cdf_client = None
        self.cdf_store = None
        self.workflow_manager = None
        self.triggers_manager = None
        logging.info("NeatApp stopped")
