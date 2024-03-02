from collections import UserList
from dataclasses import dataclass


@dataclass
class Issue:
    ...


class Error(Issue):
    ...


class Warning(Issue):
    ...


class IssueList(UserList[Issue]):
    def as_errors(self) -> ExceptionGroup:
        raise NotImplementedError()
