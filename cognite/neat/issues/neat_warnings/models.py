import sys
from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatWarning

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

_BASE_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/data-modeling-principles.html"


class DataModelingPrinciple(StrEnum):
    """Data modeling principles that are violated by a class."""

    ONE_MODEL_ONE_SPACE = "all-data-models-are-kept-in-its-own-space"
    SAME_VERSION = "all-views-of-a-data-models-have-the-same-version-and-space-as-the-data-model"
    SOLUTION_BUILDS_ON_ENTERPRISE = "solution-data-models-should-always-be-referencing-the-enterprise-data-model"

    @property
    def url(self) -> str:
        return f"{_BASE_URL}#{self.value}"


@dataclass(frozen=True)
class InvalidClassWarning(NeatWarning):
    description = "The class {class_name} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the class."

    class_name: str
    reason: str

    def message(self) -> str:
        return self.description.format(class_name=self.class_name, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["class_name"] = self.class_name
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class BreakingModelingPrincipleWarning(NeatWarning):
    """{specific} violates the {principle} principle. See {url} for more information."""

    specific: str
    principle: DataModelingPrinciple

    def message(self) -> str:
        principle = self.principle.value.replace("_", " ").title()
        return (self.__doc__ or "").format(specific=self.specific, principle=principle, url=self.principle.url)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["specific"] = self.specific
        output["principle"] = self.principle
        return output


@dataclass(frozen=True)
class UserModelingWarning(NeatWarning):
    """{title}: {problem}. {explanation}"""

    extra = "Suggestion: {suggestion}"
    title: str
    problem: str
    explanation: str
    suggestion: str | None = None

    def message(self) -> str:
        msg = (self.__doc__ or "").format(title=self.title, problem=self.problem, explanation=self.explanation)
        if self.suggestion:
            msg += f"\n{self.extra.format(suggestion=self.suggestion)}"
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["title"] = self.title
        output["problem"] = self.problem
        output["explanation"] = self.explanation
        output["suggestion"] = self.suggestion
        return output


@dataclass(frozen=True)
class CDFNotSupportedWarning(NeatWarning):
    """{title} - Will likely fail to write to CDF. {problem}."""

    extra = "Suggestion: {suggestion}"
    title: str
    problem: str
    suggestion: str | None = None

    def message(self) -> str:
        msg = (self.__doc__ or "").format(title=self.title, problem=self.problem)
        if self.suggestion:
            msg += f"\n{self.extra.format(suggestion=self.suggestion)}"
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["title"] = self.title
        output["problem"] = self.problem
        output["suggestion"] = self.suggestion
        return output
