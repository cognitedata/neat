import getpass
import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Literal, overload

from pydantic import ValidationError
from rdflib import Namespace

from cognite.neat.issues import IssueList, NeatError, NeatWarning
from cognite.neat.rules._shared import VerifiedRules
from cognite.neat.rules.models import AssetRules, DMSRules, InformationRules, RoleTypes
from cognite.neat.rules.transformers import (
    AssetToInformation,
    DMSToInformation,
    InformationToDMS,
    RulesPipeline,
)
from cognite.neat.utils.auxiliary import class_html_doc


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> VerifiedRules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[VerifiedRules | None, IssueList]: ...

    @abstractmethod
    def to_rules(
        self,
        errors: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[VerifiedRules | None, IssueList] | VerifiedRules:
        """
        Creates `Rules` object from the data for target role.
        """
        ...

    @classmethod
    def _to_output(
        cls,
        rules: VerifiedRules,
        issues: IssueList,
        errors: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[VerifiedRules | None, IssueList] | VerifiedRules:
        """Converts the rules to the output format."""

        if rules.metadata.role is role or role is None:
            output = rules
        elif isinstance(rules, DMSRules) and role is RoleTypes.information:
            output = DMSToInformation().transform(rules).rules
        elif isinstance(rules, AssetRules) and role is RoleTypes.information:
            output = AssetToInformation().transform(rules).rules
        elif isinstance(rules, InformationRules) and role is RoleTypes.dms:
            output = InformationToDMS().transform(rules).rules
        elif isinstance(rules, AssetRules) and role is RoleTypes.dms:
            output = RulesPipeline[AssetRules, DMSRules](
                [
                    AssetToInformation(),
                    InformationToDMS(),
                ]
            ).run(rules)
        else:
            raise NotImplementedError(f"Role {role} is not supported for {type(rules).__name__} rules")

        if errors == "raise":
            return output
        else:
            return output, issues

    @classmethod
    def _return_or_raise(cls, issue_list: IssueList, errors: Literal["raise", "continue"]) -> tuple[None, IssueList]:
        if errors == "raise":
            raise issue_list.as_errors()
        return None, issue_list

    def _default_metadata(self):
        return {
            "prefix": "neat",
            "schema": "partial",
            "namespace": Namespace("http://purl.org/cognite/neat/"),
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "updated": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
        }

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)


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
