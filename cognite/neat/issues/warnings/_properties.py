from dataclasses import dataclass
from typing import Generic

from cognite.neat.issues._base import NeatWarning, ResourceType

from ._resources import NeatResourceWarning, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyTypeNotSupportedWarning(NeatResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}. This will be ignored."""

    property_name: str
    property_type: str


@dataclass(frozen=True)
class PropertyNotFoundWarning(NeatResourceWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name} referred
    to by {referred_type} {referred_by} does not exist. This will be ignored.
    """

    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"
    property_name: str
    referred_by: T_ReferenceIdentifier
    referred_type: ResourceType


@dataclass(frozen=True)
class DuplicatedPropertyDefinitionWarning(NeatWarning):
    """Duplicated {name} for property {property_id}. Got multiple values: {values}.
    {default_action}"""

    extra = "Recommended action: {recommended_action}"

    property_id: str
    name: str
    values: frozenset[str]
    default_action: str
    recommended_action: str | None = None
