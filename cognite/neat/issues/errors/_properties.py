from dataclasses import dataclass
from typing import Generic

from cognite.neat.issues._base import ResourceType

from ._resources import ResourceError, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name}"""

    extra = "referred to by {referred_type} {referred_by} does not exist"
    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"

    property_name: str
    referred_by: T_ReferenceIdentifier | None = None
    referred_type: ResourceType | None = None


@dataclass(frozen=True)
class PropertyTypeNotSupportedError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}"""

    property_name: str
    property_type: str


# This is a generic error that should be used sparingly
@dataclass(frozen=True)
class PropertyDefinitionError(ResourceError[T_Identifier]):
    """Invalid property definition for {resource_type} {identifier}.{property_name}: {reason}"""

    property_name: str
    reason: str


@dataclass(frozen=True)
class DuplicatedPropertyDefinitionsError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has multiple definitions for the property {property_name}
    with values {property_values} in {location_name} {locations}
    """

    property_name: str
    property_values: frozenset[str | int | float | bool | None | tuple[str | int | float | bool | None, ...]]
    locations: tuple[str | int, ...]
    location_name: str
