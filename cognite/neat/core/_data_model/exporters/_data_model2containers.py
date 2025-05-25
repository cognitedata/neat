from pathlib import Path

from cognite.client.data_classes.data_modeling import ContainerApplyList

from cognite.neat.core._client import NeatClient
from cognite.neat.core._client._deploy import ExistingResource
from cognite.neat.core._client.data_classes.deploy_result import DeployResult
from cognite.neat.core._data_model.exporters._base import CDFExporter2
from cognite.neat.core._data_model.models import PhysicalDataModel
from cognite.neat.core._issues.errors import NeatValueError


class ContainerExporter(CDFExporter2[ContainerApplyList]):
    """Export data model to Cognite Data Fusion's Data Model Storage (DMS) service.

    Args:
        existing (Literal["fail", "skip", "update", "force", "recreate], optional): How to handle existing components.
            Defaults to "update
        drop_data (bool, optional): This must be set to True if you

    """

    def __init__(
        self,
        existing: ExistingResource = "update",
        drop_data: bool = False,
    ):
        self.existing = existing
        self.drop_data = drop_data

    @property
    def description(self) -> str:
        return "Export containers to CDF."

    def export_to_file(self, data_model: PhysicalDataModel, filepath: Path) -> None:
        """Export the data_model to a file(s).

        If the file is a directory, the components will be exported to separate files, otherwise they will be
        exported to a zip file.

        Args:
            data_model (PhysicalDataModel): The data model to export.
            filepath: Directory or zip file path to export to.

        """
        if filepath.suffix != ".yaml":
            raise NeatValueError(
                f"Cannot export containers to file. Filepath must end with .yaml, got {filepath.suffix} instead."
            )
        if filepath.exists():
            raise NeatValueError(f"Cannot export containers to file. File {filepath} already exists.")
        containers = self.export(data_model)
        filepath.write_text(containers.dump_yaml(), encoding=self._encoding, newline=self._new_line)

    def export(self, data_model: PhysicalDataModel) -> ContainerApplyList:
        # We do not want to include CogniteCore/CogniteProcess Industries in the schema
        if self.existing in {"recreate", "force"} and self.drop_data is False:
            raise NeatValueError(
                "Failed container export. Cannot export containers with "
                "exising='recreate' or 'force' without risk dropping data."
                " Set drop_data=True to proceed."
            )
        schema = data_model.as_schema(remove_cdf_spaces=True)
        return ContainerApplyList(schema.containers.values())

    def deploy(self, data_model: PhysicalDataModel, client: NeatClient, dry_run: bool = False) -> DeployResult:
        containers = self.export(data_model)
        return client.deploy(containers, dry_run=dry_run, existing=self.existing)
