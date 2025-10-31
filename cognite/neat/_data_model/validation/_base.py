from abc import ABC, abstractmethod
from typing import ClassVar

from cognite.neat._issues import ConsistencyError, Recommendation


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute the success handler on the data model."""
        # do something with data model
        pass
