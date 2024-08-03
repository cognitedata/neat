"""All warnings raised by the neat package are defined here. Note this module is called 'neat_warnings' instead
of 'warnings' to avoid conflicts with the built-in Python warnings module."""

from cognite.neat.issues._base import NeatWarning, _get_subclasses

from .external import FileMissingRequiredFieldWarning, FileReadWarning, UnexpectedFileTypeWarning, UnknownItemWarning
from .general import NeatValueWarning, NotSupportedWarning
from .identifier import RegexViolationWarning
from .models import (
    BreakingModelingPrincipleWarning,
    CDFNotSupportedWarning,
    DataModelingPrinciple,
    InvalidClassWarning,
    UserModelingWarning,
)
from .properties import (
    DuplicatedPropertyDefinitionWarning,
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
)
from .resources import (
    FailedLoadingResourcesWarning,
    MultipleResourcesWarning,
    ReferredResourceNotFoundWarning,
    ResourceNotFoundWarning,
    ResourceTypeNotSupportedWarning,
    ResourceWarning,
)

__all__ = [
    "FileReadWarning",
    "FileMissingRequiredFieldWarning",
    "UnknownItemWarning",
    "UnexpectedFileTypeWarning",
    "NeatValueWarning",
    "NotSupportedWarning",
    "RegexViolationWarning",
    "DataModelingPrinciple",
    "UserModelingWarning",
    "CDFNotSupportedWarning",
    "InvalidClassWarning",
    "BreakingModelingPrincipleWarning",
    "DuplicatedPropertyDefinitionWarning",
    "PropertyTypeNotSupportedWarning",
    "PropertyNotFoundWarning",
    "ResourceWarning",
    "MultipleResourcesWarning",
    "ResourceNotFoundWarning",
    "ReferredResourceNotFoundWarning",
    "ResourceTypeNotSupportedWarning",
    "FailedLoadingResourcesWarning",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in _get_subclasses(NeatWarning, include_base=True)}
