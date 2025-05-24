from typing import Literal, TypeAlias

from cognite.client import ClientConfig, CogniteClient
from cognite.client.data_classes._base import CogniteResourceList

from cognite.neat.core._utils.auth import _CLIENT_NAME

from ._api.crud import CrudAPI
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

        ids = crud_api.as_ids(resources)
        existing = crud_api.retrieve(ids)
        cdf_resource_by_id = {crud_api.as_id(resource): resource for resource in existing}
        local_by_id = {crud_api.as_id(resource): resource for resource in resources}

        to_create, to_update, to_delete, unchanged = (
            crud_api.list_cls([]),
            crud_api.list_cls([]),
            [],
            [],
        )

        result = DeployResult()
        for id_, local in local_by_id.items():
            cdf_resource = cdf_resource_by_id.get(id_)
            if cdf_resource is None:
                to_create.append(local)
                continue
            if existing == "skip":
                # Log in report
                continue
            if existing == "fail":
                # Log in report, mark is failing
                raise NotImplementedError()
            if existing == "recreate":
                to_delete.append(id_)
                to_create.append(local)

            if diffs := crud_api.diffs(cdf_resource, local):
                result.diffs.append(diffs)
                to_update.append(local)
            else:
                unchanged.append(id_)

        # 1. Delete. 2. Create. 3. Update.
        # 3. Perform the operations in the correct order. Include dry_run.
        # 4. If failure occurs, and restore is possible, restore the resource to its original state.
        raise NotImplementedError()
