from abc import ABC
from typing import Any, Literal

from cognite.neat._issues import IssueList, NeatError, NeatWarning, catch_issues
from cognite.neat._issues.errors import NeatTypeError
from cognite.neat._rules._shared import (
    InputRules,
    MaybeRules,
    OutRules,
    ReadRules,
    T_InputRules,
    T_VerifiedRules,
    VerifiedRules,
)
from cognite.neat._rules.models import (
    DMSInputRules,
    DMSRules,
    InformationInputRules,
    InformationRules,
)

from ._base import RulesTransformer


class VerificationTransformer(RulesTransformer[T_InputRules, T_VerifiedRules], ABC):
    """Base class for all verification transformers."""

    _rules_cls: type[T_VerifiedRules]

    def __init__(self, errors: Literal["raise", "continue"]) -> None:
        self.errors = errors

    def transform(self, rules: T_InputRules | OutRules[T_InputRules]) -> MaybeRules[T_VerifiedRules]:
        issues = IssueList()
        in_: T_InputRules = self._to_rules(rules)
        error_args: dict[str, Any] = {}
        if isinstance(rules, ReadRules):
            error_args = rules.read_context
        verified_rules: T_VerifiedRules | None = None
        with catch_issues(issues, NeatError, NeatWarning, error_args) as future:
            rules_cls = self._get_rules_cls(in_)
            verified_rules = rules_cls.model_validate(in_.dump())  # type: ignore[assignment]

        if (future.result == "failure" or issues.has_errors or verified_rules is None) and self.errors == "raise":
            raise issues.as_errors()
        return MaybeRules[T_VerifiedRules](
            rules=verified_rules,
            issues=issues,
        )

    def _get_rules_cls(self, in_: T_InputRules) -> type[T_VerifiedRules]:
        return self._rules_cls


class VerifyDMSRules(VerificationTransformer[DMSInputRules, DMSRules]):
    """Class to verify DMS rules."""

    _rules_cls = DMSRules


class VerifyInformationRules(VerificationTransformer[InformationInputRules, InformationRules]):
    """Class to verify Information rules."""

    _rules_cls = InformationRules


class VerifyAnyRules(VerificationTransformer[InputRules, VerifiedRules]):
    """Class to verify arbitrary rules"""

    def _get_rules_cls(self, in_: InputRules) -> type[VerifiedRules]:
        if isinstance(in_, InformationInputRules):
            return InformationRules
        elif isinstance(in_, DMSInputRules):
            return DMSRules
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(in_)}")
