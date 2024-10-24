from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import ResourceCreationError
from cognite.neat._rules.transformers._verification import _handle_issues


class TestIssues:
    def test_raise_issue_in_contextmanager(self) -> None:
        """Test that an issue is raised in the context manager."""
        my_error = ResourceCreationError(identifier="missing", resource_type="space", error="No CDF Connection")

        errors = IssueList()
        with _handle_issues(issues=errors):
            raise my_error

        assert errors == IssueList([my_error])
