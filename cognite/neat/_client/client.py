from cognite.client import ClientConfig, CogniteClient

from cognite.neat._utils.http_client import HTTPClient

from .config import NeatClientConfig
from .containers_api import ContainersAPI
from .data_model_api import DataModelsAPI
from .spaces_api import SpacesAPI
from .statistics_api import StatisticsAPI
from .views_api import ViewsAPI


class NeatClient:
    def __init__(self, cognite_client_or_config: CogniteClient | ClientConfig) -> None:
        self.config = NeatClientConfig(cognite_client_or_config)
        self.http_client = HTTPClient(self.config)
        self.data_models = DataModelsAPI(self.config, self.http_client)
        self.views = ViewsAPI(self.config, self.http_client)
        self.containers = ContainersAPI(self.config, self.http_client)
        self.spaces = SpacesAPI(self.config, self.http_client)
        self.statistics = StatisticsAPI(self.config, self.http_client)
