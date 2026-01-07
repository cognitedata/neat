from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._issues import ConsistencyError, Recommendation


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]
    issue_type: ClassVar[type[ConsistencyError] | type[Recommendation]]
    alpha: ClassVar[bool] = False

    def __init__(
        self,
        validation_resources: ValidationResources,
    ) -> None:
        self.validation_resources = validation_resources

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute the success handler on the data model."""
        # do something with data model
        ...
