from abc import ABC
from dataclasses import dataclass
from typing import Any

from pydantic_core import ErrorDetails

from cognite.neat.issues import MultiValueError, NeatError, NeatIssue, NeatIssueList, NeatWarning

__all__ = [
    "ValidationIssue",
    "NeatValidationError",
    "DefaultPydanticError",
    "ValidationWarning",
    "IssueList",
    "MultiValueError",
]


@dataclass(frozen=True)
class ValidationIssue(NeatIssue, ABC): ...


@dataclass(frozen=True)
class NeatValidationError(NeatError, ValidationIssue, ABC):
    @classmethod
    def from_pydantic_errors(cls, errors: list[ErrorDetails], **kwargs) -> "list[NeatValidationError]":
        """Convert a list of pydantic errors to a list of Error instances.

        This is intended to be overridden in subclasses to handle specific error types.
        """
        all_errors: list[NeatValidationError] = []
        for error in errors:
            if isinstance(ctx := error.get("ctx"), dict) and isinstance(
                multi_error := ctx.get("error"), MultiValueError
            ):
                all_errors.extend(multi_error.errors)  # type: ignore[arg-type]
            else:
                all_errors.append(DefaultPydanticError.from_pydantic_error(error))
        return all_errors


@dataclass(frozen=True)
class DefaultPydanticError(NeatValidationError):
    type: str
    loc: tuple[int | str, ...]
    msg: str
    input: Any
    ctx: dict[str, Any] | None

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> "NeatValidationError":
        return cls(
            type=error["type"],
            loc=error["loc"],
            msg=error["msg"],
            input=error.get("input"),
            ctx=error.get("ctx"),
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.type
        output["loc"] = self.loc
        output["msg"] = self.msg
        output["input"] = self.input
        output["ctx"] = self.ctx
        return output

    def message(self) -> str:
        if self.loc and len(self.loc) == 1:
            return f"{self.loc[0]} sheet: {self.msg}"
        elif self.loc and len(self.loc) == 2:
            return f"{self.loc[0]} sheet field/column <{self.loc[1]}>: {self.msg}"
        else:
            return self.msg


@dataclass(frozen=True)
class ValidationWarning(NeatWarning, ValidationIssue, ABC): ...


class IssueList(NeatIssueList[ValidationIssue]): ...
