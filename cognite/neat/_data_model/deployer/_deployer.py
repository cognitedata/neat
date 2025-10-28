from dataclasses import dataclass

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer.data_classes import SeverityType


@dataclass
class DeploymentOptions:
    """Configuration options for deployment."""

    dry_run: bool = True
    auto_rollback: bool = True
    max_severity: SeverityType = "safe"


class SchemaDeployer:
    class SchemaDeployer:
        def __init__(self, client: NeatClient, options: DeploymentOptions | None = None) -> None:
            self.client: NeatClient = client
            self.options: DeploymentOptions = options or DeploymentOptions()

        def ru(self) -> None:
            pass
