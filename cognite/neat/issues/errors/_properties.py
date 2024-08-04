from dataclasses import dataclass
from typing import Generic

from ._resources import ResourceError, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name}"""

    extra = "referred to by {referred_type} {referred_by} does not exist"
    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"

    property_name: str
    referred_by: T_ReferenceIdentifier | None = None
    referred_type: str | None = None


@dataclass(frozen=True)
class PropertyTypeNotSupportedError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}"""

    property_name: str
    property_type: str


@dataclass(frozen=True)
class InvalidPropertyDefinitionError(ResourceError[T_Identifier]):
    """Invalid property definition for {resource_type} {identifier}.{property_name}: {reason}"""

    property_name: str
    reason: str
