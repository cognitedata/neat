import warnings
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import ValidationError

from cognite.neat._utils.spreadsheet import SpreadsheetRead

from ._base import IssueList, MultiValueError, NeatError
from ._factory import from_pydantic_errors, from_warning


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
                issues.extend([from_warning(warning) for warning in warning_logger])


@contextmanager
def catch_issues(read_info_by_sheet: dict[str, SpreadsheetRead] | None = None) -> Iterator[IssueList]:
    """This is an internal help function to handle issues and warnings.

    Args:
        read_info_by_sheet (dict[str, SpreadsheetRead]): The read information by sheet. This is used to adjust
            the row numbers in the errors/warnings.

    Returns:
        IssueList: The list of issues.

    """
    with catch_warnings() as issues:
        try:
            yield issues
        except ValidationError as e:
            issues.extend(from_pydantic_errors(e.errors(), read_info_by_sheet))
        except NeatError as single:
            issues.append(single)
        except MultiValueError as multi:
            issues.extend(multi.errors)
