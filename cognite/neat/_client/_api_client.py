from cognite.client import ClientConfig, CogniteClient

from cognite.neat._utils.auth import _CLIENT_NAME

from ._api.data_modeling_loaders import DataModelLoaderAPI
from ._api.neat_instances import NeatInstancesAPI
from ._api.schema import SchemaAPI


class NeatClient(CogniteClient):
    def __init__(self, config: ClientConfig | CogniteClient | None = None) -> None:
        if isinstance(config, CogniteClient):
            config = config.config
        super().__init__(config=config)
        if self._config is not None:
            self._config.client_name = _CLIENT_NAME
        self.loaders = DataModelLoaderAPI(self)
        self.schema = SchemaAPI(self)
        self.instances = NeatInstancesAPI(self)
