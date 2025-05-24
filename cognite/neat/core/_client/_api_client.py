from collections.abc import Sequence
from typing import Literal, TypeAlias

from cognite.client import ClientConfig, CogniteClient
from cognite.client.data_classes._base import CogniteResource

from cognite.neat.core._utils.auth import _CLIENT_NAME

from ._api.data_modeling_loaders import DataModelLoaderAPI
from ._api.location_filters import LocationFiltersAPI
from ._api.neat_instances import NeatInstancesAPI
from ._api.schema import SchemaAPI
from ._api.statistics import StatisticsAPI
from .data_classes.deploy_result import DeployResult

ExistingResource: TypeAlias = Literal["skip", "fail", "update", "force", "recreate"]


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
        self.instance_statistics = StatisticsAPI(self._config, self._config.api_subversion, self)
        self.location_filters = LocationFiltersAPI(self._config, self._API_VERSION, self)

    def deploy(
        self,
        resource: CogniteResource | Sequence[CogniteResource],
        existing: ExistingResource,
        dry_run: bool = False,
        restore: bool = False,
    ) -> DeployResult:
        """Deploy a resource or a sequence of resources to CDF.

        Args:
            resource: The resource or resources to deploy.
            existing: How to handle existing resources. Options are "skip", "fail", "update", "force", and "recreate".
            dry_run: If True, only simulate the deployment without making any changes.
            restore: If True, restore the resource if it fails to deploy. This is only applicable if
                `existing` is set to "update.

        ... note::

        - "fail": Raise an error if the resource already exists.
        - "skip": Skip the resource if it already exists.
        - "update": Update the resource if it already exists. This has different behavior depending
            on the resource type.
        - "force": Tries to update the resource, but if it fails, it will recreate the resource.
        - "recreate": Recreate the resource if it already exists, regardless of its current state.

        """
        raise NotImplementedError()
