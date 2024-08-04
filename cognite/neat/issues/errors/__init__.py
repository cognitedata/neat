from cognite.neat.issues._base import DefaultPydanticError, NeatError, RowError, _get_subclasses

from ._external import (
    FailedAuthorizationError,
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileReadError,
    FileTypeUnexpectedError,
    NeatFileNotFoundError,
    NeatYamlError,
)
from ._general import NeatImportError, NeatValueError, RegexViolationError
from ._properties import (
    DuplicatedPropertyDefinitionsError,
    DuplicatedPropertyMappingError,
    PropertyDefinitionError,
    PropertyNotFoundError,
    PropertyTypeNotSupportedError,
)
from ._resources import (
    ResourceChangedError,
    ResourceConvertionError,
    ResourceCreationError,
    ResourceDuplicatedError,
    ResourceError,
    ResourceMissingIdentifierError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
    ResourceRetrievalError,
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
    "ResourceCreationError",
    "NeatFileNotFoundError",
    "FileMissingRequiredFieldError",
    "PropertyDefinitionError",
    "PropertyTypeNotSupportedError",
    "PropertyNotFoundError",
    "DuplicatedPropertyDefinitionsError",
    "ResourceChangedError",
    "ResourceDuplicatedError",
    "ResourceRetrievalError",
    "ResourceNotFoundError",
    "ResourceError",
    "ResourceNotDefinedError",
    "ResourceMissingIdentifierError",
    "ResourceConvertionError",
    "ConfigurationNotSetError",
    "WorkFlowMissingDataError",
    "StepNotInitializedError",
    "StepOutputError",
    "FileTypeUnexpectedError",
    "FileNotAFileError",
    "DefaultPydanticError",
    "DuplicatedPropertyMappingError",
    "RowError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
