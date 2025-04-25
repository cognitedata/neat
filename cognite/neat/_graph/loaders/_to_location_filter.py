from collections.abc import Iterable
from pathlib import Path

from cognite.client.data_classes.capabilities import Capability, LocationFiltersAcl
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes.location_filters import LocationFilterWrite
from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader, T_Output


class LocationFilterLoader(CDFLoader[LocationFilterWrite]):
    """Creates a location filter in CDF

    Args:
        name (str | None): Name of the location filter. If None, a default name will be generated.
        data_model_id (DataModelId | None): Data model ID for the location filter.
        instance_spaces (list[str] | None): List of instance spaces for the location filter.
        physical (DMSRules | None): Physical rules for the location filter.
    """

    def __init__(
        self,
        data_model_id: DataModelId,
        instance_spaces: list[str],
        name: str | None = None,
    ) -> None:
        self.data_model_id = data_model_id
        self.instance_spaces = instance_spaces
        self.name = name

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            LocationFiltersAcl(
                actions=[LocationFiltersAcl.Action.Read, LocationFiltersAcl.Action.Write],
                scope=LocationFiltersAcl.Scope.All(),
            )
        ]

    def _upload_to_cdf(
        self,
        client: NeatClient,
        items: list[T_Output],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        raise NotImplementedError()

    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError()

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[LocationFilterWrite | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        data_model_str = (
            f"{self.data_model_id.space}:{self.data_model_id.external_id}(version={self.data_model_id.version})"
        )
        name = self.name or f"Location Filter for {data_model_str}"
        yield LocationFilterWrite(
            external_id=name.replace(" ", "_").casefold(),
            name=name,
            description=f"Location filter for {data_model_str}",
            data_models=[self.data_model_id],
            instance_spaces=self.instance_spaces,
            data_modeling_type="DATA_MODELING_ONLY",
        )
