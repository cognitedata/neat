"""Validators checking for consistency issues in data model."""

from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-CONSISTENCY"


class ViewSpaceVersionInconsistentWithDataModel(DataModelValidator):
    """Validates that views have consistent space and version with the data model.

    ## What it does
    Validates that all views in the data model have the same space and version as the data model.

    ## Why is this bad?
    If views have different space or version than the data model, it may lead to more demanding development and
    maintenance efforts. The industry best practice is to keep views in the same space and version as the data model.

    ## Example
    If the data model is defined in space "my_space" version "v1", but a view is defined in the same spave but with
    version "v2", this requires additional attention during deployment and maintenance of the data model.
    """

    code = f"{BASE_CODE}-001"

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.local_resources.views_by_reference:
            issue_description = ""

            if view_ref.space not in COGNITE_SPACES:
                # notify about inconsisten space
                if view_ref.space != self.local_resources.data_model_reference.space:
                    issue_description = (
                        f"space (view: {view_ref.space}, data model: {self.local_resources.data_model_reference.space})"
                    )

                # or version if spaces are same
                elif view_ref.version != self.local_resources.data_model_reference.version:
                    issue_description = (
                        f"version (view: {view_ref.version}, "
                        f"data model: {self.local_resources.data_model_reference.version})"
                    )

            if issue_description:
                recommendations.append(
                    Recommendation(
                        message=(f"View {view_ref!s} has inconsistent {issue_description} with the data model."),
                        fix="Update view version and/or space to match data model",
                        code=self.code,
                    )
                )

        return recommendations
