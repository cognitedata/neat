from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from cognite.neat._rules.models import (
    DMSRules,
    InformationRules,
)
from cognite.neat._rules.models.dms._rules_input import DMSInputRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._utils.spreadsheet import SpreadsheetRead

VerifiedRules: TypeAlias = InformationRules | DMSRules

T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
InputRules: TypeAlias = DMSInputRules | InformationInputRules
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class ReadRules(Generic[T_InputRules]):
    """This represents a rules that has been read."""

    rules: T_InputRules | None
    read_context: dict[str, SpreadsheetRead]

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedModel"

    @property
    def display_name(self):
        if self.rules is None:
            return "FailedRead"
        return self.rules.display_name


ReadInputRules: TypeAlias = ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_ReadInputRules = TypeVar("T_ReadInputRules", bound=ReadInputRules)

Rules: TypeAlias = InformationRules | DMSRules | ReadRules[DMSInputRules] | ReadRules[InformationInputRules]
T_Rules = TypeVar("T_Rules", bound=Rules)
