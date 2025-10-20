from cognite.client import ClientConfig, CogniteClient


class NeatClientConfig(ClientConfig):
    def __init__(self, cognite_client_or_config: CogniteClient | ClientConfig):
        config = (
            cognite_client_or_config.config
            if isinstance(cognite_client_or_config, CogniteClient)
            else cognite_client_or_config
        )
        super().__init__(
            client_name=config.client_name,
            project=config.project,
            credentials=config.credentials,
            api_subversion=config.api_subversion,
            base_url=config.base_url,
            max_workers=config.max_workers,
            headers=config.headers,
            timeout=config.timeout,
            file_transfer_timeout=config.file_transfer_timeout,
            debug=config.debug,
        )

    def create_api_url(self, endpoint: str) -> str:
        """Create a full API URL for the given endpoint.

        Args:
            endpoint (str): The API endpoint to append to the base URL.

        Returns:
            str: The full API URL.

        Examples:
            >>> config = NeatClientConfig(cluster="bluefield", project="my_project", ...)
            >>> config.create_api_url("/models/instances")
            "https://bluefield.cognitedata.com/api/v1/my_project/models/instances"
        """
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.base_url}/api/v1/projects/{self.project}{endpoint}"
