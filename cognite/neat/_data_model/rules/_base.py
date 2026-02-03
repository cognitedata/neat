from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._issues import ConsistencyError, Recommendation


class NeatRule(ABC):
    """Base class for data model validation rules.

    Validators check data models for issues and can optionally provide fix actions.
    Each validator must define:
    - code: Unique identifier for this validation rule (e.g., "NEAT-DMS-PERFORMANCE-001")
    - issue_type: The type of issue this validator produces (ConsistencyError or Recommendation)
    - validate(): Method that returns a list of issues found

    For fixable validators, set `fixable = True` and implement the `fix()` method.

    Attributes:
        code: Unique code identifying this validator.
        issue_type: Type of issue this validator produces.
        alpha: Whether this validator is still in alpha/development.
        fixable: Whether this validator can produce fix actions.
    """

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
        """Execute rule validation.

        Returns:
            List of issues found during validation.
        """
        ...

    def fix(self) -> list[FixAction]:
        """Return fix actions for issues identified by this validator.

        Override this method in fixable validators to provide automatic fixes.
        Each FixAction represents an atomic change that can be applied to the schema.

        Returns:
            List of FixAction objects.

        Raises:
            NotImplementedError: If the validator does not implement fix().
        """
        raise NotImplementedError(f"{type(self).__name__} does not implement fix()")
