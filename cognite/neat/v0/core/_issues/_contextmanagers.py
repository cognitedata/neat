import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ._base import IssueList, MultiValueError, NeatError
from ._factory import from_pydantic_errors, from_warning

if TYPE_CHECKING:
    from cognite.neat.v0.core._data_model.models._import_contexts import ImportContext


@contextmanager
def catch_warnings() -> Iterator[IssueList]:
    """Catch warnings and append them to the issues list."""
    issues = IssueList()
    with warnings.catch_warnings(record=True) as warning_logger:
        warnings.simplefilter("always")
        try:
            yield issues
        finally:
            if warning_logger:
                issues.extend(
                    [from_warning(warning) for warning in warning_logger if from_warning(warning) is not None]
                )


@contextmanager
def catch_issues(context: "ImportContext | None" = None) -> Iterator[IssueList]:
    """This is an internal help function to handle issues and warnings.

    Args:
        context (ImportContext): The read context. This is used to adjust
            the row numbers in the errors/warnings if the data is read from a spreadsheet.

    Returns:
        IssueList: The list of issues.

    """
    with catch_warnings() as issues:
        try:
            yield issues
        except ValidationError as e:
            issues.extend(from_pydantic_errors(e.errors(), context))
        except NeatError as single:
            issues.append(single)
        except MultiValueError as multi:
            issues.extend(multi.errors)
