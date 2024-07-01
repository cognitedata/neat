"""In this test module, we are testing that the implementations of issues
are consistently implemented."""

from abc import ABC
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import GenericAlias, UnionType
from typing import Any, TypeVar

from rdflib import Namespace

from cognite.neat.rules.issues import (
    NeatValidationError,
    ValidationIssue,
    ValidationWarning,
)

T_Type = TypeVar("T_Type", bound=type)


def get_all_subclasses(cls: T_Type, only_concrete: bool = False) -> list[T_Type]:
    """Get all subclasses of a class."""
    return [
        s
        for s in cls.__subclasses__()
        if only_concrete is False or ABC not in s.__bases__
    ] + [g for s in cls.__subclasses__() for g in get_all_subclasses(s, only_concrete)]


class IssuesCreator:
    def __init__(self, data_cls: type[ValidationIssue]) -> None:
        self.data_cls = data_cls

    def create_instance(self) -> ValidationIssue:
        """Create an instance of the dataclass."""
        kwargs = {
            field.name: self._create_value(field.type)
            for field in fields(self.data_cls)
        }
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
        elif isinstance(type_, GenericAlias):
            return self._create_values(type_)
        elif isinstance(type_, UnionType):
            return self._create_value(type_.__args__[0])
        elif is_dataclass(type_):
            return IssuesCreator(type_).create_instance()
        else:
            raise NotImplementedError(f"Type {type_} not implemented.")

    def _create_values(self, field_type: GenericAlias) -> Any:
        if field_type.__origin__ is list:
            return [self._create_value(field_type.__args__[0])]
        elif field_type.__origin__ is dict:
            return {
                self._create_value(field_type.__args__[0]): self._create_value(
                    field_type.__args__[1]
                )
            }
        elif field_type.__origin__ is tuple:
            return (self._create_value(field_type.__args__[0]),)
        elif field_type.__origin__ is set:
            return {self._create_value(field_type.__args__[0])}
        elif field_type.__origin__ is frozenset:
            return frozenset({self._create_value(field_type.__args__[0])})
        elif field_type.__origin__ is type and issubclass(
            field_type.__args__[0], Warning
        ):
            return UserWarning
        else:
            raise NotImplementedError(f"Field type {field_type} not implemented.")


class TestIssuesMeta:
    def test_error_class_names_suffix_error(self) -> None:
        """Test that all classes that inherit from NeatValidationError have the suffix 'Error'."""
        errors = get_all_subclasses(NeatValidationError)

        not_error_suffix = [
            error for error in errors if not error.__name__.endswith("Error")
        ]

        assert (
            not_error_suffix == []
        ), f"Errors without 'Error' suffix: {not_error_suffix}"

    def test_warnings_class_names_suffix_warning(self) -> None:
        """Test that all classes that inherit from ValidationWarning have the suffix 'Warning'."""
        warnings = get_all_subclasses(ValidationWarning)

        not_warning_suffix = [
            warning for warning in warnings if not warning.__name__.endswith("Warning")
        ]

        assert (
            not_warning_suffix == []
        ), f"Warnings without 'Warning' suffix: {not_warning_suffix}"

    def test_all_issues_are_dataclasses(self) -> None:
        """Test that all classes that inherit from NeatValidationError or ValidationWarning are dataclasses."""
        issues = get_all_subclasses(ValidationIssue)

        not_dataclasses = [issue for issue in issues if not is_dataclass(issue)]

        assert (
            not_dataclasses == []
        ), f"Classes that are not dataclasses: {not_dataclasses}"

    def test_issues_are_sortable(self) -> None:
        """Test that all classes that inherit from ValidationIssue can be sorted with each other."""
        errors = get_all_subclasses(ValidationIssue, only_concrete=True)

        instances = [IssuesCreator(error).create_instance() for error in errors]

        assert sorted(instances)
