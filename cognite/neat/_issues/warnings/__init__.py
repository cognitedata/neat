"""All warnings raised by the neat package are defined here. Note this module is called 'warnings' which
conflicts with the built-in Python warnings module. However, it is expected to always be used in an absolute
import, and should thus not cause a naming conflict."""

from cognite.neat._issues._base import DefaultWarning, NeatWarning, _get_subclasses

from . import user_modeling
from ._external import (
    FileItemNotSupportedWarning,
    FileMissingRequiredFieldWarning,
    FileReadWarning,
    FileTypeUnexpectedWarning,
)
from ._general import NeatValueWarning, NotSupportedWarning, RegexViolationWarning
from ._models import (
    BreakingModelingPrincipleWarning,
    CDFNotSupportedWarning,
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
    PrincipleMatchingSpaceAndVersionWarning,
    PrincipleOneModelOneSpaceWarning,
    PrincipleSolutionBuildsOnEnterpriseWarning,
    UserModelingWarning,
)
from ._properties import (
    PropertyDefinitionDuplicatedWarning,
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
    PropertyValueTypeUndefinedWarning,
)
from ._resources import (
    ResourceNeatWarning,
    ResourceNotFoundWarning,
    ResourceRetrievalWarning,
    ResourcesDuplicatedWarning,
    ResourceTypeNotSupportedWarning,
)

__all__ = [
    "DefaultWarning",
    "FileReadWarning",
    "FileMissingRequiredFieldWarning",
    "FileItemNotSupportedWarning",
    "FileTypeUnexpectedWarning",
    "NeatValueWarning",
    "NotSupportedWarning",
    "UserModelingWarning",
    "CDFNotSupportedWarning",
    "BreakingModelingPrincipleWarning",
    "PropertyDefinitionDuplicatedWarning",
    "PropertyTypeNotSupportedWarning",
    "PropertyNotFoundWarning",
    "PropertyValueTypeUndefinedWarning",
    "ResourceNeatWarning",
    "ResourcesDuplicatedWarning",
    "RegexViolationWarning",
    "ResourceNotFoundWarning",
    "ResourceTypeNotSupportedWarning",
    "ResourceRetrievalWarning",
    "PrincipleOneModelOneSpaceWarning",
    "PrincipleMatchingSpaceAndVersionWarning",
    "PrincipleSolutionBuildsOnEnterpriseWarning",
    "NotSupportedViewContainerLimitWarning",
    "NotSupportedHasDataFilterLimitWarning",
    "user_modeling",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in _get_subclasses(NeatWarning, include_base=True)}
