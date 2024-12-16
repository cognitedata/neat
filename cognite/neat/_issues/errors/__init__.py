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
    "AuthorizationError",
    "CDFMissingClientError",
    "DefaultPydanticError",
    "FileMissingRequiredFieldError",
    "FileNotAFileError",
    "FileNotFoundNeatError",
    "FileReadError",
    "FileTypeUnexpectedError",
    "NeatError",
    "NeatImportError",
    "NeatTypeError",
    "NeatValueError",
    "NeatYamlError",
    "PropertyDefinitionDuplicatedError",
    "PropertyDefinitionError",
    "PropertyMappingDuplicatedError",
    "PropertyNotFoundError",
    "PropertyTypeNotSupportedError",
    "RegexViolationError",
    "ResourceChangedError",
    "ResourceConversionError",
    "ResourceCreationError",
    "ResourceDuplicatedError",
    "ResourceError",
    "ResourceMissingIdentifierError",
    "ResourceNotDefinedError",
    "ResourceNotFoundError",
    "ResourceRetrievalError",
    "ReversedConnectionNotFeasibleError",
    "RowError",
    "WorkFlowMissingDataError",
    "WorkflowConfigurationNotSetError",
    "WorkflowStepNotInitializedError",
    "WorkflowStepOutputError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
