import warnings

from cognite.client import data_modeling as dm

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import ResourceCreationError, ResourceNotDefinedError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.transformers._verification import _catch_issues


class TestIssues:
    def test_raise_issue_in_contextmanager(self) -> None:
        """Test that an issue is raised in the context manager."""
        my_error = ResourceCreationError(identifier="missing", resource_type="space", error="No CDF Connection")

        errors = IssueList()
        with _catch_issues(issues=errors):
            raise my_error

        assert errors == IssueList([my_error])

    def test_warning_in_contextmanager(self) -> None:
        """Test that a warning is caught in the context manager."""
        my_warning = NeatValueWarning("This is a warning")

        warning_list = IssueList()
        with _catch_issues(issues=warning_list):
            warnings.warn(my_warning, stacklevel=2)

        assert warning_list == IssueList([my_warning])

    def test_dump_generic_specified(self) -> None:
        my_issue = ResourceNotDefinedError[dm.ViewId](
            identifier=dm.ViewId("neat", "SKUKpi", "v1"),
            location="View Sheet",
            row_number=66,
            sheet_name="Properties",
            resource_type="view",
        )
        dumped = my_issue.dump()

        assert isinstance(dumped, dict)
