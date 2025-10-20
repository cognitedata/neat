from cognite.client import ClientConfig, CogniteClient

from cognite.neat._utils.http_client import HTTPClient

from .config import NeatClientConfig
from .data_model_api import DataModelsAPI


class NeatClient:
    def __init__(self, cognite_client_or_config: CogniteClient | ClientConfig):
        config = NeatClientConfig(cognite_client_or_config)
        http_client = HTTPClient(config)
        self.data_models = DataModelsAPI(config, http_client)
