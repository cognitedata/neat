from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

from cognite.neat._issues import IssueList
from cognite.neat._rules.models import (
    AssetRules,
    DMSRules,
    DomainRules,
    InformationRules,
)
from cognite.neat._rules.models.asset._rules_input import AssetInputRules
from cognite.neat._rules.models.dms._rules_input import DMSInputRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

VerifiedRules: TypeAlias = DomainRules | InformationRules | DMSRules | AssetRules
InputRules: TypeAlias = AssetInputRules | DMSInputRules | InformationInputRules
Rules: TypeAlias = (
    AssetInputRules | DMSInputRules | InformationInputRules | DomainRules | InformationRules | DMSRules | AssetRules
)
T_Rules = TypeVar("T_Rules", bound=Rules)
T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class OutRules(Generic[T_Rules], ABC):
    """This is a base class for all rule states."""

    @abstractmethod
    def get_rules(self) -> T_Rules | None:
        """Get the rules from the state."""
        raise NotImplementedError()


@dataclass
class JustRules(OutRules[T_Rules]):
    """This represents a rule that exists"""

    rules: T_Rules

    def get_rules(self) -> T_Rules:
        return self.rules


@dataclass
class MaybeRules(OutRules[T_Rules]):
    """This represents a rule that may or may not exist"""

    rules: T_Rules | None
    issues: IssueList

    def get_rules(self) -> T_Rules | None:
        return self.rules


@dataclass
class ReadRules(MaybeRules[T_Rules]):
    """This represents a rule that does not exist"""

    read_context: dict[str, Any]
