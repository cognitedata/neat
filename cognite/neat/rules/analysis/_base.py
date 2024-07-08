from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models.entities import ClassEntity

T_Rules = TypeVar("T_Rules", bound=Rules)


class BaseAnalysis(ABC, Generic[T_Rules]):
    @abstractmethod
    def subset_rules(self, desired_classes: set[ClassEntity]) -> T_Rules:
        raise NotImplementedError()
