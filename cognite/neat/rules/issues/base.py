from abc import ABC
from dataclasses import dataclass
from typing import Any

from pydantic_core import ErrorDetails

from cognite.neat.issues import NeatError, NeatIssue


@dataclass(frozen=True)
class ValidationIssue(NeatIssue, ABC): ...


@dataclass(frozen=True)
class NeatValidationError(NeatError, ValidationIssue, ABC): ...


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
