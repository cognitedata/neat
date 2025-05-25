from cognite.client import ClientConfig, CogniteClient
from cognite.client.data_classes._base import CogniteResourceList

from cognite.neat.core._utils.auth import _CLIENT_NAME

from ._api.crud import CrudAPI
from ._api.data_modeling_loaders import DataModelLoaderAPI
from ._api.location_filters import LocationFiltersAPI
from ._api.neat_instances import NeatInstancesAPI
from ._api.schema import SchemaAPI
from ._api.statistics import StatisticsAPI
from ._deploy import ExistingResource, deploy
from .data_classes.deploy_result import DeployResult


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
        resources: CogniteResourceList,
        existing: ExistingResource,
        dry_run: bool = False,
        restore_on_failure: bool = False,
    ) -> DeployResult:
        """Deploy a resource or a sequence of resources to CDF.

        Args:
            resources: The  resources to deploy.
            existing: How to handle existing resources. Options are "skip", "fail", "update", "force", and "recreate".
            dry_run: If True, only simulate the deployment without making any changes.
            restore_on_failure: If True, restore the resource if it fails to deploy. This is only applicable if
                `existing` is set to "update.

        ... note::

        - "fail": Raise an error if the resource already exists.
        - "skip": Skip the resource if it already exists.
        - "update": Update the resource if it already exists. This has different behavior depending
            on the resource type.
        - "force": Tries to update the resource, but if it fails, it will recreate the resource.
        - "recreate": Delete the existing resource and create a new one, regardless of whether it exists or not.

        """
        crud_api_cls = CrudAPI.get_crud_api_cls(type(resources))
        crud_api = crud_api_cls(self)
        return deploy(
            crud_api,
            resources,
            existing=existing,
            dry_run=dry_run,
            restore_on_failure=restore_on_failure,
        )
