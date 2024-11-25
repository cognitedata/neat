from cognite.client import ClientConfig, CogniteClient


class NeatClient(CogniteClient):
    def __init__(self, config: ClientConfig | None = None) -> None:
        super().__init__(config=config)
