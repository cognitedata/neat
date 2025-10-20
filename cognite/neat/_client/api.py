from cognite.neat._utils.http_client import HTTPClient


class NeatAPI:
    def __init__(self, http_client: HTTPClient) -> None:
        self._http_client = http_client
