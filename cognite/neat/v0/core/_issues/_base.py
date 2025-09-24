import inspect
import sys
import warnings
from collections.abc import Collection, Hashable, Iterable, Sequence
from dataclasses import dataclass, fields
from functools import total_ordering
from pathlib import Path
from types import UnionType
from typing import Any, ClassVar, Literal, TypeAlias, TypeVar, get_args, get_origin

import pandas as pd
from cognite.client.data_classes.data_modeling import (
    ContainerId,
    DataModelId,
    PropertyId,
    ViewId,
)

from cognite.neat.v0.core._utils.text import (
    humanize_collection,
    to_camel_case,
    to_snake_case,
)

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
    from typing_extensions import Self
else:
    from typing import Self


__all__ = [
    "IssueList",
    "MultiValueError",
    "NeatError",
    "NeatIssue",
    "NeatWarning",
]

T_Identifier = TypeVar("T_Identifier", bound=Hashable)

T_ReferenceIdentifier = TypeVar("T_ReferenceIdentifier", bound=Hashable)

ResourceType: TypeAlias = (
    Literal[
        "view",
        "container",
        "view property",
        "container property",
        "space",
        "class",
        "property",
        "asset",
        "relationship",
        "data model",
        "edge",
        "node",
        "enum collection",
        "unknown",
    ]
    # String to handle all unknown types in different importers.
    | str
)


@total_ordering
@dataclass(unsafe_hash=True)
class NeatIssue:
    """This is the base class for all exceptions and warnings (issues) used in Neat."""

    extra: ClassVar[str | None] = None
    fix: ClassVar[str | None] = None

    def as_message(self, include_type: bool = True) -> str:
        """Return a human-readable message for the issue."""
        template = self.__doc__
        if not template:
            return "Missing"
        variables, has_all_optional = self._get_variables()

        msg = template.format(**variables)
        if self.extra and has_all_optional:
            msg += "\n" + self.extra.format(**variables)
        if self.fix:
            msg += f"\nFix: {self.fix.format(**variables)}"
        if include_type:
            name = type(self).__name__
            msg = f"{name}: {msg}"
        return msg

    def _get_variables(self) -> tuple[dict[str, str], bool]:
        variables: dict[str, str] = {}
        has_all_optional = True
        for name, var_ in vars(self).items():
            if var_ is None:
                has_all_optional = False
            elif isinstance(var_, str):
                variables[name] = var_
            elif isinstance(var_, Path):
                variables[name] = var_.as_posix()
            elif isinstance(var_, Collection):
                variables[name] = humanize_collection(var_)
            elif isinstance(var_, NeatError):
                variables[name] = var_.as_message(include_type=False)
            else:
                variables[name] = repr(var_)
        return variables, has_all_optional

    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the issue."""
        variables = vars(self)
        output = {
            to_camel_case(key): self._dump_value(value)
            for key, value in variables.items()
            if not (value is None or key.startswith("_"))
        }
        output["NeatIssue"] = type(self).__name__
        return output

    @classmethod
    def _dump_value(cls, value: Any) -> list | int | bool | float | str | dict:
        from cognite.neat.v0.core._data_model.models.entities import ConceptualEntity

        if isinstance(value, str | int | bool | float):
            return value
        elif isinstance(value, frozenset):
            return [cls._dump_value(item) for item in sorted(value)]
        elif isinstance(value, Path):
            return value.as_posix()
        elif isinstance(value, tuple):
            return [cls._dump_value(item) for item in value]
        elif isinstance(value, ViewId | ContainerId):
            return value.dump(camel_case=True, include_type=True)
        elif isinstance(value, ConceptualEntity):
            return value.dump()
        elif isinstance(value, PropertyId):
            return value.dump(camel_case=True)
        elif isinstance(value, DataModelId):
            return value.dump(camel_case=True, include_type=False)
        elif isinstance(value, NeatError):
            return value.dump()
        raise ValueError(f"Unsupported type: {type(value)}")

    @classmethod
    def load(cls, data: dict[str, Any]) -> "NeatIssue":
        """Create an instance of the issue from a dictionary."""
        from cognite.neat.v0.core._issues.errors import (
            _NEAT_ERRORS_BY_NAME,
            NeatValueError,
        )
        from cognite.neat.v0.core._issues.warnings import _NEAT_WARNINGS_BY_NAME

        if "NeatIssue" not in data:
            raise NeatValueError("The data does not contain a NeatIssue key.")
        issue_type = data.pop("NeatIssue")
        args = {to_snake_case(key): value for key, value in data.items()}
        if issue_type in _NEAT_ERRORS_BY_NAME:
            return cls._load_values(_NEAT_ERRORS_BY_NAME[issue_type], args)
        elif issue_type in _NEAT_WARNINGS_BY_NAME:
            return cls._load_values(_NEAT_WARNINGS_BY_NAME[issue_type], args)
        else:
            raise NeatValueError(f"Unknown issue type: {issue_type}")

    @classmethod
    def _load_values(cls, neat_issue_cls: "type[NeatIssue]", data: dict[str, Any]) -> "NeatIssue":
        args: dict[str, Any] = {}
        for f in fields(neat_issue_cls):
            if f.name not in data:
                continue
            value = data[f.name]
            args[f.name] = cls._load_value(f.type, value)
        return neat_issue_cls(**args)

    @classmethod
    def _load_value(cls, type_: Any, value: Any) -> Any:
        from cognite.neat.v0.core._data_model.models.entities import ConceptualEntity

        if isinstance(type_, UnionType) or get_origin(type_) is UnionType:
            args = get_args(type_)
            return cls._load_value(args[0], value)
        elif type_ is frozenset or get_origin(type_) is frozenset:
            subtype = get_args(type_)[0]
            return frozenset(cls._load_value(subtype, item) for item in value)
        elif type_ is Path:
            return Path(value)
        elif type_ is tuple or get_origin(type_) is tuple:
            subtype = get_args(type_)[0]
            return tuple(cls._load_value(subtype, item) for item in value)
        elif type_ is ViewId:
            return ViewId.load(value)
        elif type_ is DataModelId:
            return DataModelId.load(value)
        elif type_ is PropertyId:
            return PropertyId.load(value)
        elif type_ is ContainerId:
            return ContainerId.load(value)
        elif inspect.isclass(type_) and issubclass(type_, ConceptualEntity):
            return type_.load(value)
        elif type_ is NeatError:
            return cls.load(value)
        return value

    def __lt__(self, other: "NeatIssue") -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.as_message()) < (type(other).__name__, other.as_message())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.as_message()) == (type(other).__name__, other.as_message())

    def __str__(self) -> str:
        return self.as_message()


@dataclass(unsafe_hash=True)
class NeatError(NeatIssue, Exception):
    """This is the base class for all exceptions (errors) used in Neat."""

    ...


@dataclass(unsafe_hash=True)
class NeatWarning(NeatIssue, UserWarning):
    """This is the base class for all warnings used in Neat."""

    ...


class MultiValueError(ValueError):
    """This is a container for multiple errors.

    It is used in the pydantic field_validator/model_validator to collect multiple errors, which
    can then be caught in a try-except block and returned as an IssueList.

    """

    def __init__(self, errors: Sequence[NeatIssue]):
        self.errors = IssueList(errors)


class IssueList(list, Sequence[NeatIssue]):
    """This is a generic list of NeatIssues."""

    def __init__(
        self,
        issues: Sequence[NeatIssue] | None = None,
        title: str | None = None,
        action: str | None = None,
        hint: str | None = None,
    ):
        super().__init__(issues or [])
        self.title = title
        self.action = action
        self.hint = hint

    def append_if_not_exist(self, issue: NeatIssue) -> None:
        """Append an issue to the list if it does not already exist."""
        if issue not in self:
            self.append(issue)

    @property
    def errors(self) -> Self:
        """Return all the errors in this list."""
        return type(self)([issue for issue in self if isinstance(issue, NeatError)])  # type: ignore[misc]

    @property
    def has_errors(self) -> bool:
        """Return True if this list contains any errors."""
        return any(isinstance(issue, NeatError) for issue in self)

    @property
    def has_warnings(self) -> bool:
        """Return True if this list contains any warnings."""
        return any(isinstance(issue, NeatWarning) for issue in self)

    @property
    def warnings(self) -> Self:
        """Return all the warnings in this list."""
        return type(self)([issue for issue in self if isinstance(issue, NeatWarning)])  # type: ignore[misc]

    def has_error_type(self, error_type: type[NeatError]) -> bool:
        """Return True if this list contains any errors of the given type."""
        return any(isinstance(issue, error_type) for issue in self)

    def has_warning_type(self, warning_type: type[NeatWarning]) -> bool:
        """Return True if this list contains any warnings of the given type."""
        return any(isinstance(issue, warning_type) for issue in self)

    def as_errors(self, operation: str = "Operation failed") -> ExceptionGroup:
        """Return an ExceptionGroup with all the errors in this list."""
        return ExceptionGroup(
            operation,
            [issue for issue in self if isinstance(issue, NeatError)],
        )

    def trigger_warnings(self) -> None:
        """Trigger all warnings in this list."""
        for warning in self.warnings:
            warnings.warn(warning, stacklevel=2)

    def to_pandas(self) -> pd.DataFrame:
        """Return a pandas DataFrame representation of this list."""
        return pd.DataFrame([issue.dump() for issue in self])

    def as_exception(self) -> MultiValueError:
        """Return a MultiValueError with all the errors in this list."""
        return MultiValueError(self.errors)

    def _repr_html_(self) -> str | None:
        if self.action and not self:
            header = f"Success: {self.action}"
        elif self.action and self.has_errors:
            header = f"Failed: {self.action}"
        elif self.action and self.has_warnings:
            header = f"Succeeded with warnings: {self.action}"
        elif not self:
            header = "No issues found"
        else:
            header = ""

        body = f"<p>{header}</p>"

        if self:
            df = self.to_pandas()
            agg_df = df["NeatIssue"].value_counts().to_frame()
            if len(agg_df) < 10:
                table = agg_df._repr_html_()  # type: ignore[operator]
            else:
                table = agg_df.head()._repr_html_()  # type: ignore[operator]
            body += f"<br />{table}"

            if self.hint:
                body += f"<br />Hint: {self.hint}"
        return body


T_Cls = TypeVar("T_Cls")


def _get_subclasses(cls_: type[T_Cls], include_base: bool = False) -> Iterable[type[T_Cls]]:
    """Get all subclasses of a class."""
    if include_base:
        yield cls_
    for s in cls_.__subclasses__():
        yield s
        yield from _get_subclasses(s, False)
