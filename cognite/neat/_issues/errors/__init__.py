from cognite.neat._issues._base import DefaultPydanticError, NeatError, RowError, _get_subclasses

from ._external import (
    AuthorizationError,
    CDFMissingClientError,
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileNotFoundNeatError,
    FileReadError,
    FileTypeUnexpectedError,
    NeatYamlError,
)
from ._general import NeatImportError, NeatTypeError, NeatValueError, RegexViolationError
from ._properties import (
    PropertyDefinitionDuplicatedError,
    PropertyDefinitionError,
    PropertyMappingDuplicatedError,
    PropertyNotFoundError,
    PropertyTypeNotSupportedError,
    ReversedConnectionNotFeasibleError,
)
from ._resources import (
    ResourceChangedError,
    ResourceConversionError,
    ResourceCreationError,
    ResourceDuplicatedError,
    ResourceError,
    ResourceMissingIdentifierError,
    ResourceNotDefinedError,
    ResourceNotFoundError,
    ResourceRetrievalError,
)
from ._workflow import (
    WorkflowConfigurationNotSetError,
    WorkFlowMissingDataError,
    WorkflowStepNotInitializedError,
    WorkflowStepOutputError,
)

__all__ = [
    "NeatError",
    "NeatValueError",
    "NeatImportError",
    "RegexViolationError",
    "AuthorizationError",
    "NeatYamlError",
    "FileReadError",
    "ResourceCreationError",
    "FileNotFoundNeatError",
    "FileMissingRequiredFieldError",
    "PropertyDefinitionError",
    "PropertyTypeNotSupportedError",
    "PropertyNotFoundError",
    "PropertyDefinitionDuplicatedError",
    "ResourceChangedError",
    "ResourceDuplicatedError",
    "ResourceRetrievalError",
    "ResourceNotFoundError",
    "ResourceError",
    "ResourceNotDefinedError",
    "ResourceMissingIdentifierError",
    "ResourceConversionError",
    "WorkflowConfigurationNotSetError",
    "WorkFlowMissingDataError",
    "WorkflowStepNotInitializedError",
    "WorkflowStepOutputError",
    "FileTypeUnexpectedError",
    "FileNotAFileError",
    "DefaultPydanticError",
    "PropertyMappingDuplicatedError",
    "RowError",
    "NeatTypeError",
    "ReversedConnectionNotFeasibleError",
    "CDFMissingClientError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
