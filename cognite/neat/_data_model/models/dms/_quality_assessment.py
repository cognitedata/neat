from cognite.neat._data_model._shared import OnSuccess
from cognite.neat._issues import ImplementationWarning

from ._schema import RequestSchema


class DmsQualityAssessment(OnSuccess):
    """Placeholder for DMS Quality Assessment functionality."""

    def run(self) -> None:
        """Run quality assessment on the DMS data model."""

        principle_assessors = DataModelPrincipleAssessors(self.data_model)
        best_practice_assessors = DataModelBestPracticeAssessors(self.data_model)

        if not principle_assessors.assess_real_use_case_alignment():
            self.issues.append(
                ImplementationWarning(
                    message="The data model does not appear to originate from real business questions.",
                    fix="Engage with stakeholders to ensure the model addresses actual business needs.",
                )
            )
        if not principle_assessors.assess_cooperation_evidence():
            self.issues.append(
                ImplementationWarning(
                    message="The data model lacks evidence of cross-domain cooperation.",
                    fix="Facilitate collaboration among different domain experts during model creation.",
                )
            )
        if not best_practice_assessors.assess_data_governance_team_exists():
            self.issues.append(
                ImplementationWarning(
                    message="No data governance team is associated with the data model.",
                    fix="Establish a data governance team to oversee model quality and compliance.",
                )
            )

        if not best_practice_assessors.assess_model_in_own_space():
            self.issues.append(
                ImplementationWarning(
                    message="The data model is not defined in its own space.",
                    fix="Define the data model in a dedicated space to avoid conflicts and ensure clarity.",
                )
            )

        if not best_practice_assessors.assess_views_same_version_and_space():
            self.issues.append(
                ImplementationWarning(
                    message="Views in the data model do not share the same version and space.",
                    fix="Ensure all views are aligned in terms of version and space for consistency.",
                )
            )


class DataModelPrincipleAssessors:
    """Assessors for fundamental data model principles."""

    def __init__(self, data_model: RequestSchema) -> None:
        self.data_model = data_model

    def assess_real_use_case_alignment(self) -> bool:
        """Does this model originate from real, active business questions?"""
        return False

    def assess_cooperation_evidence(self) -> bool:
        """Was the model co-created across domains vs solo/ivory-tower?"""
        return False

    def assess_parsimony(self) -> bool:
        """Is the model as simple as possible, but not simpler?"""
        return False


class DataModelBestPracticeAssessors:
    """Assessors for data model best practices."""

    def __init__(self, data_model: RequestSchema) -> None:
        self.data_model = data_model

    def assess_data_governance_team_exists(self) -> bool:
        return False

    def assess_model_in_own_space(self) -> bool:
        return False

    def assess_views_same_version_and_space(self) -> bool:
        return False

    def assess_model_size(self) -> bool:
        """Is data model as small as small as possible?"""
        return False
