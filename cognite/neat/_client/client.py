from cognite.client import ClientConfig, CogniteClient

from cognite.neat._utils.http_client import HTTPClient

from .data_model_api import DataModelsAPI


class NeatClient:
    def __init__(self, cognite_client_or_config: CogniteClient | ClientConfig):
        if isinstance(cognite_client_or_config, ClientConfig):
            http_client = HTTPClient(cognite_client_or_config)
        else:
            http_client = HTTPClient(cognite_client_or_config.config)
        self.data_models = DataModelsAPI(http_client)
