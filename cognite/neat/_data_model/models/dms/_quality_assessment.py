from abc import ABC, abstractmethod

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._issues import ImplementationWarning

from ._schema import RequestSchema


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        if not AssessRealUseCaseAlignment(self._client).run(data_model):
            self.issues.append(
                ImplementationWarning(
                    message="The data model does not appear to originate from real business questions.",
                    fix="Engage with stakeholders to ensure the model addresses actual business needs.",
                )
            )
        if not AssessCooperationEvidence(self._client).run(data_model):
            self.issues.append(
                ImplementationWarning(
                    message="The data model lacks evidence of cross-domain cooperation.",
                    fix="Facilitate collaboration among different domain experts during model creation.",
                )
            )


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    def __init__(self, client: NeatClient | None = None) -> None:
        self.client = client

    @abstractmethod
    def run(self, data_model: RequestSchema) -> bool:
        """Execute the success handler on the data model."""
        # do something with data model
        pass


class AssessRealUseCaseAlignment(DataModelValidator):
    """Validator for assessing real use case alignment."""

    def run(self, data_model: RequestSchema) -> bool:
        """Check if the data model is aligned with real use cases."""

        # placeholder logic, will be replaced
        return False if data_model else True


class AssessCooperationEvidence(DataModelValidator):
    """Validator for assessing cooperation evidence."""

    def run(self, data_model: RequestSchema) -> bool:
        """Check if the data model shows evidence of cooperation."""

        # placeholder logic, will be replaced
        return False if data_model else True
