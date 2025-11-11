from cognite.neat._data_model._constants import COGNITE_SPACES
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

_BASE_CODE = "NEAT-DMS-CONSISTENCY"


class VersionSpaceInconsistency(DataModelValidator):
    """This validator checks for inconsistencies in versioning and space among views and data model"""

    code = f"{_BASE_CODE}-001"

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
