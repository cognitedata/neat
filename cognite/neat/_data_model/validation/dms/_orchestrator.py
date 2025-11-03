from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import DataModelAnalysis
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._references import ViewReference
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation._base import DataModelValidator
from cognite.neat._issues import IssueList

from ._validators import UndefinedConnectionEndNodeTypes, VersionSpaceInconsistency, ViewsWithoutProperties


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self, client: NeatClient | None = None, codes: list[str] | None = None, modus_operandi: str | None = None
    ) -> None:
        self._client = client
        self._codes = codes or ["all"]
        self._modus_operandi = modus_operandi  # will be used later to trigger how validators will behave
        self._issues = IssueList()
        self._has_run = False

    @property
    def issues(self) -> IssueList:
        if not self._has_run:
            raise RuntimeError(f"{type(self).__name__} has not been run yet.")
        return IssueList(self._issues)

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""
        if self._has_run:
            raise RuntimeError(f"{type(self).__name__} has already been run.")
        # Helper wrangled data model components
        analysis = DataModelAnalysis(data_model)
        local_views_by_reference = analysis.view_by_reference(include_inherited_properties=True)
        local_connection_end_node_types = analysis.connection_end_node_types
        cdf_views_by_reference = self._cdf_view_by_reference(
            list(analysis.referenced_views(include_connection_end_node_types=True)),
            include_inherited_properties=True,
        )

        validators: list[DataModelValidator] = [
            ViewsWithoutProperties(
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
            ),
            UndefinedConnectionEndNodeTypes(
                local_connection_end_node_types=local_connection_end_node_types,
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
            ),
            VersionSpaceInconsistency(
                data_model_reference=data_model.data_model.as_reference(),
                view_references=list(local_views_by_reference.keys()),
            ),
        ]

        for validator in validators:
            if "all" in self._codes or validator.code in self._codes:
                self._issues.extend(validator.run())

        self._has_run = True

    def _cdf_view_by_reference(
        self, views: list[ViewReference], include_inherited_properties: bool = True
    ) -> dict[ViewReference, ViewRequest]:
        """Fetch view definition from CDF."""

        if not self._client:
            return {}
        return {
            response.as_reference(): response.as_request()
            for response in self._client.views.retrieve(
                views, include_inherited_properties=include_inherited_properties
            )
        }
