"""All warnings raised by the neat package are defined here. Note this module is called 'warnings' which
conflicts with the built-in Python warnings module. However, it is expected to always be used in an absolute
import, and should thus not cause a naming conflict."""

from cognite.neat.v0.core._issues._base import NeatWarning, _get_subclasses

from . import user_modeling
from ._external import (
    CDFAuthWarning,
    CDFMaxIterationsWarning,
    FileItemNotSupportedWarning,
    FileMissingRequiredFieldWarning,
    FileReadWarning,
    FileTypeUnexpectedWarning,
)
from ._general import (
    DeprecatedWarning,
    MissingCogniteClientWarning,
    NeatValueWarning,
    NotSupportedWarning,
    RegexViolationWarning,
)
from ._models import (
    BreakingModelingPrincipleWarning,
    CDFNotSupportedWarning,
    ConversionToPhysicalModelImpossibleWarning,
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
    PropertyDefinitionWarning,
    PropertyDirectRelationLimitWarning,
    PropertyMultipleValueWarning,
    PropertyNotFoundWarning,
    PropertyOverwritingWarning,
    PropertyTypeNotSupportedWarning,
    PropertyValueTypeUndefinedWarning,
    ReversedConnectionNotFeasibleWarning,
)
from ._resources import (
    ResourceNeatWarning,
    ResourceNotFoundWarning,
    ResourceRegexViolationWarning,
    ResourceRetrievalWarning,
    ResourcesDuplicatedWarning,
    ResourceTypeNotSupportedWarning,
    ResourceUnknownWarning,
)

__all__ = [
    "BreakingModelingPrincipleWarning",
    "CDFAuthWarning",
    "CDFMaxIterationsWarning",
    "CDFNotSupportedWarning",
    "ConversionToPhysicalModelImpossibleWarning",
    "DeprecatedWarning",
    "FileItemNotSupportedWarning",
    "FileMissingRequiredFieldWarning",
    "FileReadWarning",
    "FileTypeUnexpectedWarning",
    "MissingCogniteClientWarning",
    "NeatValueWarning",
    "NotSupportedHasDataFilterLimitWarning",
    "NotSupportedViewContainerLimitWarning",
    "NotSupportedWarning",
    "PrincipleMatchingSpaceAndVersionWarning",
    "PrincipleOneModelOneSpaceWarning",
    "PrincipleSolutionBuildsOnEnterpriseWarning",
    "PropertyDataTypeConversionWarning",
    "PropertyDefinitionDuplicatedWarning",
    "PropertyDefinitionWarning",
    "PropertyDirectRelationLimitWarning",
    "PropertyMultipleValueWarning",
    "PropertyNotFoundWarning",
    "PropertyOverwritingWarning",
    "PropertyTypeNotSupportedWarning",
    "PropertyValueTypeUndefinedWarning",
    "RegexViolationWarning",
    "ResourceNeatWarning",
    "ResourceNotFoundWarning",
    "ResourceRegexViolationWarning",
    "ResourceRetrievalWarning",
    "ResourceTypeNotSupportedWarning",
    "ResourceUnknownWarning",
    "ResourcesDuplicatedWarning",
    "ReversedConnectionNotFeasibleWarning",
    "UndefinedViewWarning",
    "UserModelingWarning",
    "user_modeling",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in _get_subclasses(NeatWarning, include_base=True)}
