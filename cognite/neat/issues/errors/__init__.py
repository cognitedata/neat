from cognite.neat.issues._base import DefaultPydanticError, InvalidRowError, NeatError, _get_subclasses

from ._external import (
    FailedAuthorizationError,
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileReadError,
    InvalidYamlError,
    NeatFileNotFoundError,
    UnexpectedFileTypeError,
)
from ._general import NeatImportError, NeatValueError, RegexViolationError
from ._properties import (
    InvalidPropertyDefinitionError,
    PropertyNotFoundError,
    PropertyTypeNotSupportedError,
)
from ._resources import (
    ChangedResourceError,
    DuplicatedMappingError,
    DuplicatedPropertyDefinitionsError,
    DuplicatedResourceError,
    FailedConvertError,
    InvalidResourceError,
    MissingIdentifierError,
    ReferredResourceNotFoundError,
    ResourceError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
)
from ._workflow import ConfigurationNotSetError, InvalidStepOutputError, InvalidWorkFlowError, StepNotInitializedError

__all__ = [
    "NeatError",
    "NeatValueError",
    "NeatImportError",
    "RegexViolationError",
    "FailedAuthorizationError",
    "InvalidYamlError",
    "FileReadError",
    "NeatFileNotFoundError",
    "FileMissingRequiredFieldError",
    "InvalidPropertyDefinitionError",
    "PropertyTypeNotSupportedError",
    "PropertyNotFoundError",
    "DuplicatedPropertyDefinitionsError",
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
    "UnexpectedFileTypeError",
    "FileNotAFileError",
    "DefaultPydanticError",
    "InvalidRowError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
