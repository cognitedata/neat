import warnings

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.v0.core._issues import IssueList, catch_issues, catch_warnings
from cognite.neat.v0.core._issues.errors import (
    NeatValueError,
    PropertyValueError,
    ResourceCreationError,
    ResourceNotDefinedError,
)
from cognite.neat.v0.core._issues.warnings import NeatValueWarning


class TestIssues:
    def test_raise_issue_in_contextmanager(self) -> None:
        """Test that an issue is raised in the context manager."""
        my_error = ResourceCreationError(identifier="missing", resource_type="space", error="No CDF Connection")

        with catch_issues() as errors:
            raise my_error

        assert errors == IssueList([my_error])

    def test_warning_in_contextmanager(self) -> None:
        """Test that a warning is caught in the context manager."""
        my_warning = NeatValueWarning("This is a warning")

        with catch_warnings() as warning_list:
            warnings.warn(my_warning, stacklevel=2)

        assert warning_list == IssueList([my_warning])

    def test_raise_error_in_warning_contextmanager(self) -> None:
        """Test that an error is raised in the warning context manager."""
        with pytest.raises(ResourceCreationError):
            with catch_warnings() as warning_list:
                raise ResourceCreationError(identifier="missing", resource_type="space", error="No CDF Connection")

        assert len(warning_list) == 0

    def test_dump_generic_specified(self) -> None:
        my_issue = ResourceNotDefinedError(
            identifier=dm.ViewId("neat", "SKUKpi", "v1"),
            location="View Sheet",
            row_number=66,
            sheet_name="Properties",
            resource_type="view",
        )
        dumped = my_issue.dump()

        assert isinstance(dumped, dict)

    def test_wrapper_issue_as_message(self) -> None:
        issue = PropertyValueError(row=4, column="Is List", error=NeatValueError("Expected a bool type, got 'Apple'"))
        assert issue.as_message(include_type=False) == "In row 4, column 'Is List': Expected a bool type, got 'Apple'"
