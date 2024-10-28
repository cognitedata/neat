from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from cognite.client.data_classes.data_modeling import ViewId

from cognite.neat._constants import DMS_VIEW_CONTAINER_SIZE_LIMIT
from cognite.neat._issues import NeatWarning

_BASE_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/data-modeling-principles.html"


@dataclass(unsafe_hash=True)
class BreakingModelingPrincipleWarning(NeatWarning, ABC):
    """{warning_class}: {specific} violates the {principle} principle.
    See {url} for more information."""

    url: ClassVar[str]
    specific: str

    def as_message(self) -> str:
        principle = type(self).__name__.removesuffix("Warning")
        url = f"{_BASE_URL}#{self.url}"
        return (self.__doc__ or "").format(
            warning_class=BreakingModelingPrincipleWarning.__name__,
            specific=self.specific,
            principle=principle,
            url=url,
        )


@dataclass(unsafe_hash=True)
class PrincipleOneModelOneSpaceWarning(BreakingModelingPrincipleWarning):
    """{warning_class}: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "all-data-models-are-kept-in-its-own-space"


@dataclass(unsafe_hash=True)
class PrincipleMatchingSpaceAndVersionWarning(BreakingModelingPrincipleWarning):
    """{warning_class}: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "all-views-of-a-data-models-have-the-same-version-and-space-as-the-data-model"


@dataclass(unsafe_hash=True)
class PrincipleSolutionBuildsOnEnterpriseWarning(BreakingModelingPrincipleWarning):
    """{warning_class}: {specific} violates the {principle} principle.
    See {url} for more information."""

    url = "solution-data-models-should-always-be-referencing-the-enterprise-data-model"


@dataclass(unsafe_hash=True)
class UserModelingWarning(NeatWarning, ABC):
    """This is a generic warning for user modeling issues.
    These warnings will not cause the resulting model to be invalid, but
    will likely lead to suboptimal performance, unnecessary complexity, or other issues."""

    ...


@dataclass(unsafe_hash=True)
class CDFNotSupportedWarning(NeatWarning, ABC):
    """This is a base class for warnings for modeling issues that will
    likely lead to the CDF API rejecting the model."""

    ...


@dataclass(unsafe_hash=True)
class NotSupportedViewContainerLimitWarning(CDFNotSupportedWarning):
    """The view {view_id} maps, {count} containers, which is more than the limit {limit}."""

    fix = "Reduce the number of containers the view maps to." ""

    view_id: ViewId
    count: int
    limit: int = DMS_VIEW_CONTAINER_SIZE_LIMIT


@dataclass(unsafe_hash=True)
class NotSupportedHasDataFilterLimitWarning(CDFNotSupportedWarning):
    """The view {view_id} uses a hasData filter applied to {count} containers, which is more than the limit {limit}."""

    fix = "Do not map to more than {limit} containers."

    view_id: ViewId
    count: int
    limit: int = DMS_VIEW_CONTAINER_SIZE_LIMIT
