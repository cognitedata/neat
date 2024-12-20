"""All warnings raised by the neat package are defined here. Note this module is called 'warnings' which
conflicts with the built-in Python warnings module. However, it is expected to always be used in an absolute
import, and should thus not cause a naming conflict."""

from cognite.neat._issues._base import DefaultWarning, NeatWarning, _get_subclasses

from . import user_modeling
from ._external import (
    CDFAuthWarning,
    CDFMaxIterationsWarning,
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
    UndefinedViewWarning,
    UserModelingWarning,
)
from ._properties import (
    PropertyDataTypeConversionWarning,
    PropertyDefinitionDuplicatedWarning,
    PropertyNotFoundWarning,
    PropertyOverwritingWarning,
    PropertySkippedWarning,
    PropertyTypeNotSupportedWarning,
    PropertyValueTypeUndefinedWarning,
)
from ._resources import (
    ResourceNeatWarning,
    ResourceNotFoundWarning,
    ResourceRegexViolationWarning,
    ResourceRetrievalWarning,
    ResourcesDuplicatedWarning,
    ResourceTypeNotSupportedWarning,
)

__all__ = [
    "BreakingModelingPrincipleWarning",
    "CDFAuthWarning",
    "CDFMaxIterationsWarning",
    "CDFNotSupportedWarning",
    "DefaultWarning",
    "FileItemNotSupportedWarning",
    "FileMissingRequiredFieldWarning",
    "FileReadWarning",
    "FileTypeUnexpectedWarning",
    "NeatValueWarning",
    "NotSupportedHasDataFilterLimitWarning",
    "NotSupportedViewContainerLimitWarning",
    "NotSupportedWarning",
    "PrincipleMatchingSpaceAndVersionWarning",
    "PrincipleOneModelOneSpaceWarning",
    "PrincipleSolutionBuildsOnEnterpriseWarning",
    "PropertyDataTypeConversionWarning",
    "PropertyDefinitionDuplicatedWarning",
    "PropertyNotFoundWarning",
    "PropertyOverwritingWarning",
    "PropertySkippedWarning",
    "PropertyTypeNotSupportedWarning",
    "PropertyValueTypeUndefinedWarning",
    "RegexViolationWarning",
    "ResourceNeatWarning",
    "ResourceNotFoundWarning",
    "ResourceRegexViolationWarning",
    "ResourceRetrievalWarning",
    "ResourceTypeNotSupportedWarning",
    "ResourcesDuplicatedWarning",
    "UndefinedViewWarning",
    "UserModelingWarning",
    "user_modeling",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in _get_subclasses(NeatWarning, include_base=True)}
