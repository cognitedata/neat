"""In this test module, we are testing that the implementations of issues
are consistently implemented."""

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import fields, is_dataclass

import pytest
from _pytest.mark import ParameterSet

from cognite.neat.v0.core._issues import NeatError, NeatIssue, NeatWarning
from cognite.neat.v0.core._issues.errors import (
    ResourceChangedError,
    ResourceNotFoundError,
    SpreadsheetError,
)
from tests.v0.utils import DataClassCreator, get_all_subclasses


@pytest.fixture(scope="session")
def issue_classes() -> list[type[NeatIssue]]:
    return get_all_subclasses(NeatIssue, only_concrete=True)


@pytest.fixture(scope="session")
def issue_instances(issue_classes) -> list[NeatIssue]:
    return [DataClassCreator(cls_).create_instance() for cls_ in issue_classes]


def issue_instances_iterator() -> Iterable[ParameterSet]:
    for cls_ in get_all_subclasses(NeatIssue, only_concrete=True):
        yield pytest.param(DataClassCreator(cls_).create_instance(), id=cls_.__name__)


class TestIssuesMeta:
    def test_error_class_names_suffix_error(self) -> None:
        """Test that all classes that inherit from NeatError have the suffix 'Error'."""
        errors = get_all_subclasses(NeatError)

        not_error_suffix = [error for error in errors if not error.__name__.endswith("Error")]

        assert not_error_suffix == [], f"Errors without 'Error' suffix: {not_error_suffix}"

    def test_errors_subclass_exception(self) -> None:
        """Test that all classes that inherit from NeatError are exceptions.
        Note NeatError is an Exception, and each error should subclass a more
        specific exception in addition to NeatError.
        """
        errors = get_all_subclasses(NeatError)

        not_exception = [
            error
            for error in errors
            if not any(issubclass(base, Exception) and base is not NeatError for base in error.__bases__)
        ]

        assert not_exception == [], f"Errors that are not exceptions: {not_exception}"

    def test_warnings_class_names_suffix_warning(self) -> None:
        """Test that all classes that inherit from NeatWarning have the suffix 'Warning'."""
        warnings = get_all_subclasses(NeatWarning)

        not_warning_suffix = [warning for warning in warnings if not warning.__name__.endswith("Warning")]

        assert not_warning_suffix == [], f"Warnings without 'Warning' suffix: {not_warning_suffix}"

    def test_all_issues_are_dataclasses(self, issue_classes: list[type[NeatIssue]]) -> None:
        """Test that all classes that inherit from NeatIssue are dataclasses."""
        not_dataclasses = [issue for issue in issue_classes if not is_dataclass(issue)]

        assert not_dataclasses == [], f"Classes that are not dataclasses: {not_dataclasses}"

    def test_all_issue_names_unique(self, issue_classes: list[type[NeatIssue]]) -> None:
        """Test that all classes that inherit from NeatIssue are unique."""
        duplicates = [name for name, count in Counter([issue.__name__ for issue in issue_classes]).items() if count > 1]

        assert duplicates == [], f"Duplicate classes: {duplicates}"

    def test_required_variables_in_docstrings(self, issue_classes: list[type[NeatIssue]]) -> None:
        """Test that all classes that inherit from NeatIssue have all variables in the docstring."""
        missing_variables = [
            (issue.__name__, missing)
            for issue in issue_classes
            if (
                missing := [
                    field.name
                    for field in fields(issue)
                    if f"{{{field.name}}}" not in (issue.__doc__ or "") and field.default is not None
                ]
                # Exclude ChangedResourceError as it has a custom as_message method.
                and issue not in {ResourceChangedError}
                # All SpreadsheetErrors have their own as_message method.
                and not issubclass(issue, SpreadsheetError)
            )
        ]
        assert missing_variables == [], f"Variables missing in docstring: {missing_variables}"

    def test_optional_variables_in_extra(self, issue_classes: list[type[NeatIssue]]) -> None:
        """Test that all classes that inherit from NeatIssue have all optional variables in the extra attribute."""
        missing_extra = [
            (issue.__name__, missing)
            for issue in issue_classes
            if issue.extra is not None
            # Exception as it has a custom as_message method.
            and issue not in {ResourceNotFoundError}
            and (
                missing := [
                    field.name
                    for field in fields(issue)
                    if f"{{{field.name}}}" not in issue.extra and field.default is None
                ]
            )
        ]
        assert missing_extra == [], f"Variables missing in extra: {missing_extra}"

    def test_issues_are_sortable(self, issue_instances: list[NeatIssue]) -> None:
        """Test that all classes that inherit from NeatIssue can be sorted with each other."""
        assert sorted(issue_instances)

    @pytest.mark.parametrize("issue", issue_instances_iterator())
    def test_issues_message(self, issue: NeatIssue) -> None:
        """Test that all classes that inherit from NeatIssue have a message."""
        message = issue.as_message()
        assert isinstance(message, str)
        assert message != "", f"Empty message for {issue.__class__.__name__}"

    @pytest.mark.parametrize("issue", issue_instances_iterator())
    def test_issues_hashable(self, issue: NeatIssue) -> None:
        """Test that all classes that inherit from NeatIssue are hashable."""
        hash(issue)

    @pytest.mark.parametrize("issue", issue_instances_iterator())
    def test_issues_dump_load(self, issue: NeatIssue) -> None:
        """Test that all classes that inherit from ValidationIssue can be dumped and loaded."""
        dumped = issue.dump()
        assert isinstance(dumped, dict)
        assert dumped != {}, f"Empty dump for {issue.__class__.__name__}"
        # Ensure that the dump can be serialized and deserialized
        json_dumped = json.dumps(dumped)
        json_loaded = json.loads(json_dumped)
        loaded = NeatIssue.load(json_loaded)

        assert issue == loaded, f"Dump and load mismatch for {issue.__class__.__name__}"
