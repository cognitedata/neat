from cognite.neat._client.config import NeatClientConfig
from cognite.neat._utils.http_client import HTTPClient


class NeatAPI:
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        self._config = neat_config
        self._http_client = http_client
