from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import DataModelAnalysis
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._references import ViewReference
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._issues import ConsistencyError

from ._schema import RequestSchema


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]

    @abstractmethod
    def run(self) -> list[ConsistencyError]:
        """Execute the success handler on the data model."""
        # do something with data model
        pass


class ViewsWithoutProperties(DataModelValidator):
    """This validator checks for views without properties, i.e. views that do not have any
    property attached to them , either directly or through implements."""

    code = "NEAT-DMS-001"

    def __init__(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest] | None = None,
    ) -> None:
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference or {}

    def run(self) -> list[ConsistencyError]:
        """Check if the data model is aligned with real use cases."""

        views_without_properties = []

        for ref, view in self.local_views_by_reference.items():
            if not view.properties:
                # Existing CDF view has properties
                if (
                    self.cdf_views_by_reference
                    and (remote := self.cdf_views_by_reference.get(ref))
                    and remote.properties
                ):
                    continue

                # Implemented views have properties
                if view.implements and any(
                    self.cdf_views_by_reference
                    and (remote_implement := self.cdf_views_by_reference.get(implement))
                    and remote_implement.properties
                    for implement in view.implements or []
                ):
                    continue

                views_without_properties.append(ref)

        return [
            ConsistencyError(
                message=(
                    f"View {ref!s} does "
                    "not have any properties defined, either directly or through implements."
                    " This will prohibit your from deploying the data model to CDF."
                ),
                fix="Define properties for the view",
            )
            for ref in views_without_properties
        ]


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self, client: NeatClient | None = None, codes: list[str] | None = None, modus_operandi: str | None = None
    ) -> None:
        super().__init__(client)
        self._codes = codes or ["all"]
        self._modus_operandi = modus_operandi  # will be used later to trigger how validators will behave

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        local_views_by_reference = DataModelAnalysis(data_model).view_by_reference(include_inherited_properties=True)
        cdf_views_by_reference = self._cdf_view_by_reference(
            list(DataModelAnalysis(data_model).referenced_views), include_inherited_properties=True
        )

        validators: list[DataModelValidator] = [
            ViewsWithoutProperties(
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
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
