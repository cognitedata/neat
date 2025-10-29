from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import DataModelAnalysis
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._references import DataModelReference, ViewReference
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._issues import ConsistencyError, Recommendation

from ._schema import RequestSchema


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation]:
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
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

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
                code=self.code,
            )
            for ref in views_without_properties
        ]


class UndefinedConnectionEndNodeTypes(DataModelValidator):
    """This validator checks for connections where the end node types are not defined"""

    code = "NEAT-DMS-002"

    def __init__(
        self,
        local_connection_end_node_types: dict[tuple[ViewReference, str], ViewReference],
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> None:
        self.local_connection_end_node_types = local_connection_end_node_types
        self.local_views_by_reference = local_views_by_reference
        self.cdf_views_by_reference = cdf_views_by_reference

    def run(self) -> list[ConsistencyError]:
        """Check if the data model is aligned with real use cases."""

        undefined_value_types = []

        for (view, property_), value_type in self.local_connection_end_node_types.items():
            if value_type not in self.local_views_by_reference and value_type not in self.cdf_views_by_reference:
                undefined_value_types.append((view, property_, value_type))

        return [
            ConsistencyError(
                message=(
                    f"View {view!s} property {property_!s} has value type {value_type!s} "
                    "which is not defined as a view in the data model neither exists in CDF."
                    " This will prohibit you from deploying the data model to CDF."
                ),
                fix="Define necessary view",
                code=self.code,
            )
            for (view, property_, value_type) in undefined_value_types
        ]


class VersionSpaceInconsistency(DataModelValidator):
    """This validator checks for inconsistencies in versioning and space among views and data model"""

    code = "NEAT-DMS-003"

    def __init__(
        self,
        data_model_reference: DataModelReference,
        view_references: list[ViewReference],
    ) -> None:
        self.data_model_reference = data_model_reference
        self.view_references = view_references

    def run(self) -> list[Recommendation]:
        """Check if the data model is aligned with real use cases."""

        recommendations = []

        for view_ref in self.view_references:
            issues = []

            if view_ref.version != self.data_model_reference.version:
                issues.append(f"version (view: {view_ref.version}, data model: {self.data_model_reference.version})")

            if view_ref.space != self.data_model_reference.space:
                issues.append(f"space (view: {view_ref.space}, data model: {self.data_model_reference.space})")

            if issues:
                issue_description = " and ".join(issues)
                recommendations.append(
                    Recommendation(
                        message=(
                            f"View {view_ref!s} has inconsistent {issue_description} "
                            "with the data model."
                            " This may lead to more demanding development and maintenance efforts."
                        ),
                        fix="Update view version and/or space to match data model",
                        code=self.code,
                    )
                )

        return recommendations


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
