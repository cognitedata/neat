from dataclasses import dataclass
from typing import Generic

from cognite.neat._issues._base import ResourceType

from ._resources import ResourceError, T_Identifier, T_ReferenceIdentifier


@dataclass(unsafe_hash=True)
class PropertyError(ResourceError[T_Identifier]):
    """Base class for property errors {resource_type} with identifier {identifier}.{property_name}"""

    property_name: str


@dataclass(unsafe_hash=True)
class PropertyNotFoundError(PropertyError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name}"""

    extra = "referred to by {referred_type} {referred_by} does not exist"
    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"

    referred_by: T_ReferenceIdentifier | None = None
    referred_type: ResourceType | None = None


@dataclass(unsafe_hash=True)
class PropertyTypeNotSupportedError(PropertyError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}"""

    property_type: str


@dataclass(unsafe_hash=True)
class ReversedConnectionNotFeasibleError(PropertyError[T_Identifier]):
    """The {resource_type} {property_name} with identifier {identifier} of the view {target_view_id} cannot be made
    since view {source_view_id} does not have direct connection {direct_connection} defined,
    or {direct_connection} value type is not {target_view_id}
    """

    target_view_id: str
    source_view_id: str
    direct_connection: str


# This is a generic error that should be used sparingly
@dataclass(unsafe_hash=True)
class PropertyDefinitionError(PropertyError[T_Identifier]):
    """Invalid property definition for {resource_type} {identifier}.{property_name}: {reason}"""

    reason: str


@dataclass(unsafe_hash=True)
class PropertyDefinitionDuplicatedError(PropertyError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has multiple definitions for the property {property_name}
    with values {property_values}
    """

    extra = "in locations {locations} with name {location_name}"

    property_values: frozenset[str | int | float | bool | None | tuple[str | int | float | bool | None, ...]]
    locations: tuple[str | int, ...] | None = None
    location_name: str | None = None


@dataclass(unsafe_hash=True)
class PropertyMappingDuplicatedError(PropertyError[T_Identifier], Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier}.{property_name} is mapped to by: {mappings}. Ensure
    that only one {mapping_type} maps to {resource_type} {identifier}.{property_name}"""

    mappings: frozenset[T_ReferenceIdentifier]
    mapping_type: ResourceType
