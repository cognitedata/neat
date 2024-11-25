from cognite.client import ClientConfig, CogniteClient

from ._api.data_modeling_loaders import DataModelLoaderAPI


class NeatClient(CogniteClient):
    def __init__(self, config: ClientConfig | CogniteClient | None = None) -> None:
        if isinstance(config, CogniteClient):
            config = config.config
        super().__init__(config=config)
        self.loaders = DataModelLoaderAPI(self)
