"""This is module contains all the Neat Exceptions (Errors) and Warnings as well
as some helper classes to handle them like NeatIssueList"""

from ._base import (
    DefaultWarning,
    IssueList,
    MultiValueError,
    NeatError,
    NeatIssue,
    NeatIssueList,
    NeatWarning,
    catch_issues,
    catch_warnings,
)
from .errors._factory import from_pydantic


__all__ = [
    "DefaultWarning",
    "IssueList",
    "MultiValueError",
    "NeatError",
    "NeatIssue",
    "NeatIssueList",
    "NeatWarning",
    "from_pydantic",
    "catch_issues",
    "catch_warnings",
]
