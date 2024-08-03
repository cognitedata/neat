import sys
from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from cognite.neat.issues import NeatWarning

if sys.version_info >= (3, 11):
    pass
else:
    pass

_BASE_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/data-modeling-principles.html"


@dataclass(frozen=True)
class InvalidClassWarning(NeatWarning):
    """The {class_name} is invalid and will be skipped. {reason}"""

    fix = "Check the error message and correct the class."

    class_name: str
    reason: str


@dataclass(frozen=True)
class BreakingModelingPrincipleWarning(NeatWarning, ABC):
    """BreakingModelingPrincipleWarning: {specific} violates the {principle} principle.
    See {url} for more information."""

    url: ClassVar[str]
    specific: str

    def as_message(self) -> str:
        principle = type(self).__name__.removesuffix("Warning")
        url = f"{_BASE_URL}#{self.url}"
        return (self.__doc__ or "").format(specific=self.specific, principle=principle, url=url)


@dataclass(frozen=True)
class OneModelOneSpaceWarning(BreakingModelingPrincipleWarning):
    """BreakingModelingPrincipleWarning: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "all-data-models-are-kept-in-its-own-space"


@dataclass(frozen=True)
class MatchingSpaceAndVersionWarning(BreakingModelingPrincipleWarning):
    """BreakingModelingPrincipleWarning: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "all-views-of-a-data-models-have-the-same-version-and-space-as-the-data-model"


@dataclass(frozen=True)
class SolutionBuildsOnEnterpriseWarning(BreakingModelingPrincipleWarning):
    """BreakingModelingPrincipleWarning: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "solution-data-models-should-always-be-referencing-the-enterprise-data-model"


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
