import warnings
from abc import ABC
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from pydantic import ValidationError

from cognite.neat._issues import IssueList, MultiValueError, NeatError, NeatWarning
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
    AssetInputRules,
    AssetRules,
    DMSInputRules,
    DMSRules,
    DomainInputRules,
    DomainRules,
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
        with _handle_issues(issues, NeatError, NeatWarning, error_args) as future:
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


class VerifyAssetRules(VerificationTransformer[AssetInputRules, AssetRules]):
    """Class to verify Asset rules."""

    _rules_cls = AssetRules


class VerifyAnyRules(VerificationTransformer[InputRules, VerifiedRules]):
    """Class to verify arbitrary rules"""

    def _get_rules_cls(self, in_: InputRules) -> type[VerifiedRules]:
        if isinstance(in_, InformationInputRules):
            return InformationRules
        elif isinstance(in_, DMSInputRules):
            return DMSRules
        elif isinstance(in_, AssetInputRules):
            return AssetRules
        elif isinstance(in_, DomainInputRules):
            return DomainRules
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(in_)}")


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
        except MultiValueError as e:
            issues.extend(e.errors)
            future_result._result = "failure"
        except NeatError as e:
            issues.append(e)
            future_result._result = "failure"
        else:
            future_result._result = "success"
        finally:
            if warning_logger:
                issues.extend([warning_cls.from_warning(warning) for warning in warning_logger])  # type: ignore[misc]
