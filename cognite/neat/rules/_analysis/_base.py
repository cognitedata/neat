from abc import ABC, abstractmethod

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules._types import ClassEntity


class BaseAnalysis(ABC):
    @abstractmethod
    def subset_rules(self, desired_classes: set[ClassEntity]) -> Rules:
        raise NotImplementedError()
