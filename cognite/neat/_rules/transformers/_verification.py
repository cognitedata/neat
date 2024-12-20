from abc import ABC

from cognite.neat._client import NeatClient
from cognite.neat._issues import IssueList, MultiValueError, NeatError, NeatWarning, catch_issues
from cognite.neat._issues.errors import NeatTypeError, NeatValueError
from cognite.neat._rules._shared import (
    ReadRules,
    T_ReadInputRules,
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


class VerificationTransformer(RulesTransformer[T_ReadInputRules, T_VerifiedRules], ABC):
    """Base class for all verification transformers."""

    _rules_cls: type[T_VerifiedRules]
    _validation_cls: type

    def __init__(self, validate: bool = True, client: NeatClient | None = None) -> None:
        self.validate = validate
        self._client = client

    def transform(self, rules: T_ReadInputRules) -> T_VerifiedRules:
        in_ = rules.rules
        if in_ is None:
            raise NeatValueError("Cannot verify rules. The reading of the rules failed.")
        error_args = rules.read_context
        verified_rules: T_VerifiedRules | None = None
        # We need to catch issues as we use the error args to provide extra context for the errors/warnings
        # For example, which row in the spreadsheet the error occurred o
        issues = IssueList()
        with catch_issues(issues, NeatError, NeatWarning, error_args) as _:
            rules_cls = self._get_rules_cls(rules)
            dumped = in_.dump()
            verified_rules = rules_cls.model_validate(dumped)  # type: ignore[assignment]
            if self.validate:
                validation_cls = self._get_validation_cls(verified_rules)  # type: ignore[arg-type]
                if issubclass(validation_cls, DMSValidation):
                    validation_issues = DMSValidation(verified_rules, self._client).validate()  # type: ignore[arg-type]
                elif issubclass(validation_cls, InformationValidation):
                    validation_issues = InformationValidation(verified_rules).validate()  # type: ignore[arg-type]
                else:
                    raise NeatValueError("Unsupported rule type")

                # Need to trigger and raise such that the catch_issues can add the extra context
                validation_issues.trigger_warnings()
                if validation_issues.has_errors:
                    raise MultiValueError(validation_issues.errors)

        # Raise issues which is expected to be handled outside of this method
        issues.trigger_warnings()
        if issues.has_errors:
            raise MultiValueError(issues.errors)
        if verified_rules is None:
            raise NeatValueError("Rules were not verified")
        return verified_rules

    def _get_rules_cls(self, in_: T_ReadInputRules) -> type[T_VerifiedRules]:
        return self._rules_cls

    def _get_validation_cls(self, rules: T_VerifiedRules) -> type:
        return self._validation_cls

    @property
    def description(self) -> str:
        return "Verify rules"


class VerifyDMSRules(VerificationTransformer[ReadRules[DMSInputRules], DMSRules]):
    """Class to verify DMS rules."""

    _rules_cls = DMSRules
    _validation_cls = DMSValidation

    def transform(self, rules: ReadRules[DMSInputRules]) -> DMSRules:
        return super().transform(rules)


class VerifyInformationRules(VerificationTransformer[ReadRules[InformationInputRules], InformationRules]):
    """Class to verify Information rules."""

    _rules_cls = InformationRules
    _validation_cls = InformationValidation

    def transform(self, rules: ReadRules[InformationInputRules]) -> InformationRules:
        return super().transform(rules)


class VerifyAnyRules(VerificationTransformer[T_ReadInputRules, VerifiedRules]):
    """Class to verify arbitrary rules"""

    def _get_rules_cls(self, in_: T_ReadInputRules) -> type[VerifiedRules]:
        if isinstance(in_.rules, InformationInputRules):
            return InformationRules
        elif isinstance(in_.rules, DMSInputRules):
            return DMSRules
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(in_)}")

    def _get_validation_cls(self, rules: VerifiedRules) -> type:
        if isinstance(rules, InformationRules):
            return InformationValidation
        elif isinstance(rules, DMSRules):
            return DMSValidation
        else:
            raise NeatTypeError(f"Unsupported rules type: {type(rules)}")
