import warnings
from abc import ABC
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from pydantic import ValidationError

from cognite.neat.issues import IssueList, NeatError, NeatWarning
from cognite.neat.rules._shared import T_InputRules, T_VerifiedRules
from cognite.neat.rules.models import (
    AssetRules,
    AssetRulesInput,
    DMSRules,
    DMSRulesInput,
    InformationRules,
    InformationRulesInput,
)

from ._base import MaybeRules, OutRules, ReadRules, RulesTransformer


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
        with _handle_issues(issues, NeatError, NeatWarning, error_args) as future:
            verified_rules = self._rules_cls.model_validate(in_.dump())  # type: ignore[assignment]

        if (future.result == "failure" or issues.has_errors or verified_rules is None) and self.errors == "raise":
            raise issues.as_errors()
        return MaybeRules(
            rule=verified_rules,
            issues=issues,
        )


class VerifyDMSRules(VerificationTransformer[DMSRulesInput, DMSRules]):
    """Class to verify DMS rules."""

    _rules_cls = DMSRules


class VerifyInformationRules(VerificationTransformer[InformationRulesInput, InformationRules]):
    """Class to verify Information rules."""

    _rules_cls = InformationRules


class VerifyAssetRules(VerificationTransformer[AssetRulesInput, AssetRules]):
    """Class to verify Asset rules."""

    _rules_cls = AssetRules


class _FutureResult:
    def __init__(self) -> None:
        self._result: Literal["success", "failure", "pending"] = "pending"

    @property
    def result(self) -> Literal["success", "failure", "pending"]:
        return self._result


@contextmanager
def _handle_issues(
    issues: IssueList,
    error_cls: type[NeatError] = NeatError,
    warning_cls: type[NeatWarning] = NeatWarning,
    error_args: dict[str, Any] | None = None,
) -> Iterator[_FutureResult]:
    """This is an internal help function to handle issues and warnings.

    Args:
        issues: The issues list to append to.
        error_cls: The class used to convert errors to issues.
        warning_cls:  The class used to convert warnings to issues.

    Returns:
        FutureResult: A future result object that can be used to check the result of the context manager.
    """
    with warnings.catch_warnings(record=True) as warning_logger:
        warnings.simplefilter("always")
        future_result = _FutureResult()
        try:
            yield future_result
        except ValidationError as e:
            issues.extend(error_cls.from_pydantic_errors(e.errors(), **(error_args or {})))
            future_result._result = "failure"
        else:
            future_result._result = "success"
        finally:
            if warning_logger:
                issues.extend([warning_cls.from_warning(warning) for warning in warning_logger])  # type: ignore[misc]
