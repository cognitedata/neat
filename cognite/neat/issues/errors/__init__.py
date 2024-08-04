from cognite.neat.issues._base import DefaultPydanticError, NeatError, RowError, _get_subclasses

from ._external import (
    FailedAuthorizationError,
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileReadError,
    NeatFileNotFoundError,
    NeatYamlError,
    UnexpectedFileTypeError,
)
from ._general import NeatImportError, NeatValueError, RegexViolationError
from ._properties import (
    DuplicatedPropertyDefinitionsError,
    PropertyDefinitionError,
    PropertyNotFoundError,
    PropertyTypeNotSupportedError,
)
from ._resources import (
    ChangedResourceError,
    DuplicatedMappingError,
    DuplicatedResourceError,
    FailedConvertError,
    MissingIdentifierError,
    ResourceError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
    ResourceValueError,
    RetrievalResourceError,
)
from ._workflow import ConfigurationNotSetError, StepNotInitializedError, StepOutputError, WorkFlowMissingDataError

__all__ = [
    "NeatError",
    "NeatValueError",
    "NeatImportError",
    "RegexViolationError",
    "FailedAuthorizationError",
    "NeatYamlError",
    "FileReadError",
    "NeatFileNotFoundError",
    "FileMissingRequiredFieldError",
    "PropertyDefinitionError",
    "PropertyTypeNotSupportedError",
    "PropertyNotFoundError",
    "DuplicatedPropertyDefinitionsError",
    "ChangedResourceError",
    "DuplicatedResourceError",
    "RetrievalResourceError",
    "ResourceNotFoundError",
    "DuplicatedMappingError",
    "ResourceError",
    "ResourceNotDefinedError",
    "ResourceValueError",
    "MissingIdentifierError",
    "FailedConvertError",
    "ConfigurationNotSetError",
    "WorkFlowMissingDataError",
    "StepNotInitializedError",
    "StepOutputError",
    "UnexpectedFileTypeError",
    "FileNotAFileError",
    "DefaultPydanticError",
    "RowError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
