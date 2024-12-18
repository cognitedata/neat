from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

from cognite.neat._rules.models import (
    DMSRules,
    InformationRules,
)
from cognite.neat._rules.models.dms._rules_input import DMSInputRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

VerifiedRules: TypeAlias = InformationRules | DMSRules
InputRules: TypeAlias = DMSInputRules | InformationInputRules
T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
T_InputRules = TypeVar("T_InputRules", bound=InputRules)

@dataclass
class ReadRules(Generic[T_InputRules]):
    """This represents a rules that has been read."""

    rules: T_InputRules | None
    read_context: dict[str, Any]

Rules: TypeAlias = DMSInputRules | InformationInputRules | InformationRules | DMSRules | ReadRules
T_Rules = TypeVar("T_Rules", bound=Rules)

