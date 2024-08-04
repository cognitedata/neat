"""In this test module, we are testing that the implementations of issues
are consistently implemented."""

import json
from abc import ABC
from collections import Counter
from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import GenericAlias, UnionType
from typing import Any, TypeVar, get_args

import pytest
from _pytest.mark import ParameterSet
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from rdflib import Namespace

from cognite.neat.issues import NeatError, NeatIssue, NeatWarning
from cognite.neat.issues.errors import ChangedResourceError

T_Type = TypeVar("T_Type", bound=type)


def get_all_subclasses(cls: T_Type, only_concrete: bool = False) -> list[T_Type]:
    """Get all subclasses of a class."""
    return [s for s in cls.__subclasses__() if only_concrete is False or ABC not in s.__bases__] + [
        g for s in cls.__subclasses__() for g in get_all_subclasses(s, only_concrete)
    ]


class IssuesCreator:
    def __init__(self, data_cls: type[NeatIssue]) -> None:
        self.data_cls = data_cls

    def create_instance(self) -> NeatIssue:
        """Create an instance of the dataclass."""
        kwargs = {field.name: self._create_value(field.type) for field in fields(self.data_cls)}
        return self.data_cls(**kwargs)

    def _create_value(self, type_: type) -> Any:
        if type_ is str or isinstance(type_, str):
            return "string"
        elif type_ is Any:
            return "any"
        elif type_ is int:
            return 1
        elif type_ is float:
            return 1.0
        elif type_ is bool:
            return True
        elif type_ is Path:
            return Path("path")
        elif type_ is Namespace:
            return Namespace("http://purl.org/cognite/neat/issue#")
        elif type_ == list[tuple[str, str]]:
            return [("Class", "Property")]
        elif isinstance(type_, GenericAlias):
            return self._create_values(type_)
        elif isinstance(type_, UnionType):
            return self._create_value(type_.__args__[0])
        elif type(type_) is TypeVar or any(type(arg) is TypeVar for arg in get_args(type_)):
            return "typevar"
        elif type_ is ViewId:
            return ViewId("namespace", "class", "version")
        elif type_ is ContainerId:
            return ContainerId("namespace", "class")
        else:
            raise NotImplementedError(f"Type {type_} not implemented.")

    def _create_values(self, field_type: GenericAlias) -> Any:
        if field_type.__origin__ is list:
            return [self._create_value(field_type.__args__[0])]
        elif field_type.__origin__ is dict:
            return {self._create_value(field_type.__args__[0]): self._create_value(field_type.__args__[1])}
        elif field_type.__origin__ is tuple:
            return (self._create_value(field_type.__args__[0]),)
        elif field_type.__origin__ is set:
            return {self._create_value(field_type.__args__[0])}
        elif field_type.__origin__ is frozenset:
            return frozenset({self._create_value(field_type.__args__[0])})
        elif field_type.__origin__ is type and issubclass(field_type.__args__[0], Warning):
            return UserWarning
        else:
            raise NotImplementedError(f"Field type {field_type} not implemented.")


@pytest.fixture(scope="session")
def issue_classes() -> list[type[NeatIssue]]:
    return get_all_subclasses(NeatIssue, only_concrete=True)


@pytest.fixture(scope="session")
def issue_instances(issue_classes) -> list[NeatIssue]:
    return [IssuesCreator(cls_).create_instance() for cls_ in issue_classes]


def issue_instances_iterator() -> Iterable[ParameterSet]:
    for cls_ in get_all_subclasses(NeatIssue, only_concrete=True):
        yield pytest.param(IssuesCreator(cls_).create_instance(), id=cls_.__name__)


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
                and issue not in {ChangedResourceError}
            )
        ]
        assert missing_variables == [], f"Variables missing in docstring: {missing_variables}"

    def test_optional_variables_in_extra(self, issue_classes: list[type[NeatIssue]]) -> None:
        """Test that all classes that inherit from NeatIssue have all optional variables in the extra attribute."""
        missing_extra = [
            (issue.__name__, missing)
            for issue in issue_classes
            if issue.extra is not None
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
