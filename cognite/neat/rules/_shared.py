from abc import ABC
from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

from cognite.neat.issues import IssueList
from cognite.neat.rules.models import (
    AssetRules,
    DMSRules,
    DomainRules,
    InformationRules,
)
from cognite.neat.rules.models.asset._rules_input import AssetRulesInput
from cognite.neat.rules.models.dms._rules_input import DMSInputRules
from cognite.neat.rules.models.information._rules_input import InformationRulesInput

VerifiedRules: TypeAlias = DomainRules | InformationRules | DMSRules | AssetRules
InputRules: TypeAlias = AssetRulesInput | DMSInputRules | InformationRulesInput
Rules: TypeAlias = (
    AssetRulesInput | DMSInputRules | InformationRulesInput | DomainRules | InformationRules | DMSRules | AssetRules
)
T_Rules = TypeVar("T_Rules", bound=Rules)
T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class OutRules(Generic[T_Rules], ABC):
    """This is a base class for all rule states."""


@dataclass
class JustRules(OutRules[T_Rules]):
    """This represents a rule that exists"""

    rules: T_Rules


@dataclass
class MaybeRules(OutRules[T_Rules]):
    """This represents a rule that may or may not exist"""

    rules: T_Rules | None
    issues: IssueList


@dataclass
class ReadRules(MaybeRules[T_Rules]):
    """This represents a rule that does not exist"""

    read_context: dict[str, Any]
