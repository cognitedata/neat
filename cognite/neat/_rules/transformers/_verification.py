from abc import ABC
from typing import Any, Literal

from cognite.neat._issues import IssueList, MultiValueError, NeatError, NeatWarning, catch_issues
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
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.models.information import InformationValidation

from ._base import RulesTransformer


class VerificationTransformer(RulesTransformer[T_InputRules, T_VerifiedRules], ABC):
    """Base class for all verification transformers."""

    _rules_cls: type[T_VerifiedRules]
    _validation_cls: type

    def __init__(self, errors: Literal["raise", "continue"], validate: bool = True) -> None:
        self.errors = errors
        self.validate = validate

    def transform(self, rules: T_InputRules | OutRules[T_InputRules]) -> MaybeRules[T_VerifiedRules]:
        issues = IssueList()
        in_: T_InputRules = self._to_rules(rules)
        error_args: dict[str, Any] = {}
        if isinstance(rules, ReadRules):
            error_args = rules.read_context
        verified_rules: T_VerifiedRules | None = None
        with catch_issues(issues, NeatError, NeatWarning, error_args) as future:
            rules_cls = self._get_rules_cls(in_)
            dumped = in_.dump()
            verified_rules = rules_cls.model_validate(dumped)  # type: ignore[assignment]
            if self.validate:
                validation_cls = self._get_validation_cls(verified_rules)  # type: ignore[arg-type]
                validation_issues = validation_cls(verified_rules).validate()
                # We need to trigger warnings are raise exceptions such that they are caught by the context manager
                # and processed with the read context
                if validation_issues.warnings:
                    validation_issues.trigger_warnings()
                if validation_issues.has_errors:
                    verified_rules = None
                    raise MultiValueError(validation_issues.errors)

        if (future.result == "failure" or issues.has_errors or verified_rules is None) and self.errors == "raise":
            raise issues.as_errors()
        return MaybeRules[T_VerifiedRules](
            rules=verified_rules,
            issues=issues,
        )

    def _get_rules_cls(self, in_: T_InputRules) -> type[T_VerifiedRules]:
        return self._rules_cls

    def _get_validation_cls(self, rules: T_VerifiedRules) -> type:
        return self._validation_cls


class VerifyDMSRules(VerificationTransformer[DMSInputRules, DMSRules]):
    """Class to verify DMS rules."""

    _rules_cls = DMSRules
    _validation_cls = DMSValidation


class VerifyInformationRules(VerificationTransformer[InformationInputRules, InformationRules]):
    """Class to verify Information rules."""

    _rules_cls = InformationRules
    _validation_cls = InformationValidation


class VerifyAnyRules(VerificationTransformer[InputRules, VerifiedRules]):
    """Class to verify arbitrary rules"""

    def _get_rules_cls(self, in_: InputRules) -> type[VerifiedRules]:
        if isinstance(in_, InformationInputRules):
            return InformationRules
        elif isinstance(in_, DMSInputRules):
            return DMSRules
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(in_)}")

    def _get_validation_cls(self, rules: T_VerifiedRules) -> type:
        if isinstance(rules, InformationRules):
            return InformationValidation
        elif isinstance(rules, DMSRules):
            return DMSValidation
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(rules)}")
