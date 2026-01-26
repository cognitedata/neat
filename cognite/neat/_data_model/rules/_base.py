from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._issues import ConsistencyError, Recommendation


class DataModelRule(ABC):
    """Rules for data model principles."""

    code: ClassVar[str]
    issue_type: ClassVar[type[ConsistencyError] | type[Recommendation]]
    alpha: ClassVar[bool] = False
    fixable: ClassVar[bool] = False

    def __init__(
        self,
        validation_resources: ValidationResources,
    ) -> None:
        self.validation_resources = validation_resources

    @abstractmethod
    def validate(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute rule validation."""
        ...

    def fix(self) -> RequestSchema:
        """Fix the issues found by the validator producing a fixed object."""

        raise NotImplementedError("This rule does not implement fix()")
