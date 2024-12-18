from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

from jedi.plugins.stdlib import Wrapped

from cognite.neat._rules.models import (
    DMSRules,
    InformationRules,
)
from cognite.neat._rules.models.dms._rules_input import DMSInputRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

VerifiedRules: TypeAlias = InformationRules | DMSRules

T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
InputRules: TypeAlias = DMSInputRules | InformationInputRules
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class ReadRules(Generic[T_InputRules]):
    """This represents a rules that has been read."""

    rules: T_InputRules | None
    read_context: dict[str, Any]


WrappedInputRules: TypeAlias = ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_WrappedInputRules = TypeVar("T_WrappedInputRules", bound=WrappedInputRules)

Rules: TypeAlias = InformationRules | DMSRules | ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_Rules = TypeVar("T_Rules", bound=Rules)
