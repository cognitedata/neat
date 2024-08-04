"""All warnings raised by the neat package are defined here. Note this module is called 'neat_warnings' instead
of 'warnings' to avoid conflicts with the built-in Python warnings module."""

from cognite.neat.issues._base import DefaultWarning, NeatWarning, _get_subclasses

from . import user_modeling
from ._external import FileMissingRequiredFieldWarning, FileReadWarning, UnexpectedFileTypeWarning, UnknownItemWarning
from ._general import NeatValueWarning, NotSupportedWarning, RegexViolationWarning
from ._models import (
    BreakingModelingPrincipleWarning,
    CDFNotSupportedWarning,
    HasDataFilterLimitWarning,
    MatchingSpaceAndVersionWarning,
    OneModelOneSpaceWarning,
    SolutionBuildsOnEnterpriseWarning,
    UserModelingWarning,
    ViewContainerLimitWarning,
)
from ._properties import (
    DuplicatedPropertyDefinitionWarning,
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
)
from ._resources import (
    DuplicatedResourcesWarning,
    FailedRetrievingResourcesWarning,
    NeatResourceWarning,
    ResourceNotFoundWarning,
    ResourceTypeNotSupportedWarning,
)

__all__ = [
    "DefaultWarning",
    "FileReadWarning",
    "FileMissingRequiredFieldWarning",
    "UnknownItemWarning",
    "UnexpectedFileTypeWarning",
    "NeatValueWarning",
    "NotSupportedWarning",
    "UserModelingWarning",
    "CDFNotSupportedWarning",
    "BreakingModelingPrincipleWarning",
    "DuplicatedPropertyDefinitionWarning",
    "PropertyTypeNotSupportedWarning",
    "PropertyNotFoundWarning",
    "NeatResourceWarning",
    "DuplicatedResourcesWarning",
    "RegexViolationWarning",
    "ResourceNotFoundWarning",
    "ResourceTypeNotSupportedWarning",
    "FailedRetrievingResourcesWarning",
    "OneModelOneSpaceWarning",
    "MatchingSpaceAndVersionWarning",
    "SolutionBuildsOnEnterpriseWarning",
    "ViewContainerLimitWarning",
    "HasDataFilterLimitWarning",
    "user_modeling",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in _get_subclasses(NeatWarning, include_base=True)}
