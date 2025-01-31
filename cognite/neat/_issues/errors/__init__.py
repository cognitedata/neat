from cognite.neat._issues._base import NeatError, _get_subclasses

from ._external import (
    AuthorizationError,
    CDFMissingClientError,
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileNotFoundNeatError,
    FileReadError,
    FileTypeUnexpectedError,
    NeatYamlError,
    OxigraphStorageLockedError,
)
from ._general import NeatImportError, NeatTypeError, NeatValueError, RegexViolationError
from ._model import MetadataValueError
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
from ._wrapper import (
    ClassValueError,
    ContainerValueError,
    EnumValueError,
    MetadataValueError,
    NodeValueError,
    PropertyValueError,
    SpreadsheetError,
    ViewValueError,
)

__all__ = [
    "AuthorizationError",
    "CDFMissingClientError",
    "ClassValueError",
    "ContainerValueError",
    "EnumValueError",
    "FileMissingRequiredFieldError",
    "FileNotAFileError",
    "FileNotFoundNeatError",
    "FileReadError",
    "FileTypeUnexpectedError",
    "MetadataValueError",
    "NeatError",
    "NeatImportError",
    "NeatTypeError",
    "NeatValueError",
    "NeatYamlError",
    "NodeValueError",
    "OxigraphStorageLockedError",
    "PropertyDefinitionDuplicatedError",
    "PropertyDefinitionError",
    "PropertyMappingDuplicatedError",
    "PropertyNotFoundError",
    "PropertyTypeNotSupportedError",
    "PropertyValueError",
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
    "SpreadsheetError",
    "ViewValueError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in _get_subclasses(NeatError, include_base=True)}
