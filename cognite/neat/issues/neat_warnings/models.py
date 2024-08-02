import sys
from dataclasses import dataclass

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


@dataclass(frozen=True)
class BreakingModelingPrincipleWarning(NeatWarning):
    """{specific} violates the {principle} principle. See {url} for more information."""

    specific: str
    principle: DataModelingPrinciple


@dataclass(frozen=True)
class UserModelingWarning(NeatWarning):
    """{title}: {problem}. {explanation}"""

    extra = "Suggestion: {suggestion}"
    title: str
    problem: str
    explanation: str
    suggestion: str | None = None


@dataclass(frozen=True)
class CDFNotSupportedWarning(NeatWarning):
    """{title} - Will likely fail to write to CDF. {problem}."""

    extra = "Suggestion: {suggestion}"
    title: str
    problem: str
    suggestion: str | None = None
