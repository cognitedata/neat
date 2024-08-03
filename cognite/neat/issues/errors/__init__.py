from cognite.neat.issues._base import NeatError, _get_subclasses

from .external import (
    FailedAuthorizationError,
    FileMissingRequiredFieldError,
    FileReadError,
    InvalidYamlError,
    NeatFileNotFoundError,
)
from .general import MissingRequiredFieldError, NeatImportError, NeatValueError, RegexViolationError
from .properties import (
    InvalidPropertyDefinitionError,
    PropertyNotFoundError,
    PropertyTypeNotSupportedError,
    ReferredPropertyNotFoundError,
)
from .resources import (
    ChangedResourceError,
    DuplicatedMappingError,
    DuplicatedResourceError,
    FailedConvertError,
    InvalidResourceError,
    MissingIdentifierError,
    MultiplePropertyDefinitionsError,
    ReferredResourceNotFoundError,
    ResourceError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
)
from .workflow import ConfigurationNotSetError, InvalidStepOutputError, InvalidWorkFlowError, StepNotInitializedError

__all__ = [
    "MissingRequiredFieldError",
    "NeatValueError",
    "NeatImportError",
    "RegexViolationError",
    "FailedAuthorizationError",
    "InvalidYamlError",
    "FileReadError",
    "NeatFileNotFoundError",
    "FileMissingRequiredFieldError",
    "InvalidPropertyDefinitionError",
    "PropertyNotFoundError",
    "PropertyTypeNotSupportedError",
    "ReferredPropertyNotFoundError",
    "MultiplePropertyDefinitionsError",
    "ChangedResourceError",
    "DuplicatedResourceError",
    "ResourceNotFoundError",
    "ReferredResourceNotFoundError",
    "DuplicatedMappingError",
    "ResourceError",
    "ResourceNotDefinedError",
    "InvalidResourceError",
    "MissingIdentifierError",
    "FailedConvertError",
    "ConfigurationNotSetError",
    "InvalidWorkFlowError",
    "StepNotInitializedError",
    "InvalidStepOutputError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
