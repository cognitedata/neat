import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime
from typing import Any, Generic, Literal

from pydantic import ValidationError
from rdflib import Namespace

from cognite.neat._issues import IssueList, NeatError, NeatWarning
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._utils.auxiliary import class_html_doc


class BaseImporter(ABC, Generic[T_InputRules]):
    """
    BaseImporter class which all importers inherit from.
    """

    @abstractmethod
    def to_rules(self) -> ReadRules[T_InputRules]:
        """Creates `Rules` object from the data for target role."""
        raise NotImplementedError()

    def _default_metadata(self) -> dict[str, Any]:
        creator = "UNKNOWN"
        with suppress(KeyError, ImportError):
            import getpass

            creator = getpass.getuser()

        return {
            "prefix": "neat",
            "schema": "partial",
            "namespace": Namespace("http://purl.org/cognite/neat/"),
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "updated": datetime.now().replace(microsecond=0).isoformat(),
            "creator": creator,
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
