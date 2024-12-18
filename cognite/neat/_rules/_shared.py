from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

from cognite.neat._rules.models import (
    DMSRules,
    InformationRules,
)
from cognite.neat._rules.models.dms._rules_input import DMSInputRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

VerifiedRules: TypeAlias = InformationRules | DMSRules

T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
T_PureInputRules = TypeVar("T_PureInputRules", bound=DMSInputRules | InformationInputRules)


@dataclass
class ReadRules(Generic[T_PureInputRules]):
    """This represents a rules that has been read."""

    rules: T_PureInputRules | None
    read_context: dict[str, Any]


InputRules: TypeAlias = ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_InputRules = TypeVar("T_InputRules", bound=InputRules)

Rules: TypeAlias = InformationRules | DMSRules | ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_Rules = TypeVar("T_Rules", bound=Rules)
