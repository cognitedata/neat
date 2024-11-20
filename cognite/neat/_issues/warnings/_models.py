from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from cognite.client.data_classes.data_modeling import DataModelId, ViewId

from cognite.neat._constants import DMS_VIEW_CONTAINER_SIZE_LIMIT
from cognite.neat._issues import NeatWarning

_BASE_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/data-modeling-principles.html"


@dataclass(unsafe_hash=True)
class BreakingModelingPrincipleWarning(NeatWarning, ABC):
    """{warning_class}: {specific} violates the {principle} principle.
    See {url} for more information."""

    url: ClassVar[str]
    specific: str

    def as_message(self, include_type: bool = True) -> str:
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


@dataclass(unsafe_hash=True)
class UndefinedClassWarning(UserModelingWarning):
    """Class {class_id} has no explicit properties defined neither implements other class"""

    fix = "Define properties for class or inherit properties by implementing another class."

    class_id: str


@dataclass(unsafe_hash=True)
class UndefinedViewWarning(UserModelingWarning):
    """Undefined view {value_type} has been referred as value type for property <{view_property}> of view {view_id}."""

    fix = "Define views which are used as value types."

    view_id: str
    value_type: str
    view_property: str


@dataclass(unsafe_hash=True)
class EnterpriseModelNotBuildOnTopOfCDMWarning(UserModelingWarning):
    """Enterprise data model being build on top {reference_model_id}. This is not recommended."""

    fix = "Always build Enterprise Data Model on top of Cognite Data Model such as Core Data Model."

    reference_model_id: DataModelId


@dataclass(unsafe_hash=True)
class SolutionModelBuildOnTopOfCDMWarning(UserModelingWarning):
    """Solution data model being build on top Cognite Data Model {reference_model_id}. This is not recommended."""

    fix = "Always build solution data model on top of enterprise data model."

    reference_model_id: DataModelId
