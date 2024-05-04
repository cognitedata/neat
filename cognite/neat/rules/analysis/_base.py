import sys
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models.entities import ClassEntity

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

T_Rules = TypeVar("T_Rules", bound=Rules)


class BaseAnalysis(ABC, Generic[T_Rules]):
    @abstractmethod
    def subset_rules(self, desired_classes: set[ClassEntity]) -> T_Rules:
        raise NotImplementedError()


class DataModelingScenario(StrEnum):
    from_scratch = "from scratch"
    build_solution = "build solution"
    extend_reference = "extend reference"
