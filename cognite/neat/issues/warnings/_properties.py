from dataclasses import dataclass
from typing import Generic

from cognite.neat.issues._base import ResourceType

from ._resources import ResourceNeatWarning, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyWarning(ResourceNeatWarning[T_Identifier]):
    """Base class for property warnings {resource_type} with identifier {identifier}.{property_name}"""

    property_name: str


@dataclass(frozen=True)
class PropertyTypeNotSupportedWarning(PropertyWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}. This will be ignored."""

    property_type: str


@dataclass(frozen=True)
class PropertyNotFoundWarning(PropertyWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name} referred
    to by {referred_type} {referred_by} does not exist. This will be ignored.
    """

    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"
    referred_by: T_ReferenceIdentifier
    referred_type: ResourceType


@dataclass(frozen=True)
class PropertyDefinitionDuplicatedWarning(PropertyWarning[T_Identifier]):
    """Got multiple values for the {resource_type} {identifier}.{property_name} {values}.
    {default_action}"""

    extra = "Recommended action: {recommended_action}"

    values: frozenset[str]
    default_action: str
    recommended_action: str | None = None
