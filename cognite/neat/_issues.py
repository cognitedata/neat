from collections import UserList, defaultdict

from pydantic import BaseModel


class Issue(BaseModel):
    """Base class for all issues"""

    message: str


class ModelSyntaxError(Issue):
    """If any syntax error is found. Stop validation
    and ask user to fix the syntax error first."""

    ...


class ImplementationWarning(Issue):
    """This is only for conceptual data model. It means that conversion to DMS
    will fail unless user implements the missing part."""

    message: str
    fix: str


class ConsistencyError(Issue):
    """If any consistency error is found, the deployment of the data model will fail. For example,
    if a reverse direct relations points to a non-existing direct relation. This is only relevant for
    DMS model.
    """

    message: str
    fix: str


class Recommendation(Issue):
    """Best practice recommendation."""

    message: str
    fix: str | None = None


class IssueList(UserList[Issue]):
    """A list of issues that can be sorted by type and message."""

    def by_type(self) -> dict[type[Issue], list[Issue]]:
        """Returns a dictionary of issues sorted by their type."""
        result: dict[type[Issue], list[Issue]] = defaultdict(list)
        for issue in self.data:
            issue_type = type(issue)
            if issue_type not in result:
                result[issue_type] = []
            result[issue_type].append(issue)
        return result
