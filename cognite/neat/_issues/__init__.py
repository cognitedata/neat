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

__all__ = [
    "DefaultWarning",
    "IssueList",
    "MultiValueError",
    "NeatError",
    "NeatIssue",
    "NeatIssueList",
    "NeatWarning",
    "catch_issues",
    "catch_warnings",
]
