from cognite.client import ClientConfig, CogniteClient

from cognite.neat._utils.http_client import HTTPClient

from .config import NeatClientConfig
from .containers_api import ContainersAPI
from .data_model_api import DataModelsAPI
from .spaces_api import SpacesAPI
from .views_api import ViewsAPI


class NeatClient:
    def __init__(self, cognite_client_or_config: CogniteClient | ClientConfig):
        self.config = NeatClientConfig(cognite_client_or_config)
        http_client = HTTPClient(self.config)
        self.data_models = DataModelsAPI(self.config, http_client)
        self.views = ViewsAPI(self.config, http_client)
        self.containers = ContainersAPI(self.config, http_client)
        self.spaces = SpacesAPI(self.config, http_client)
