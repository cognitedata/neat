from dataclasses import dataclass
from typing import Generic

from cognite.neat._constants import DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT
from cognite.neat._issues._base import ResourceType

from ._resources import ResourceNeatWarning, T_Identifier, T_ReferenceIdentifier


@dataclass(unsafe_hash=True)
class PropertyWarning(ResourceNeatWarning[T_Identifier]):
    """Base class for property warnings {resource_type} with identifier {identifier}.{property_name}"""

    property_name: str


@dataclass(unsafe_hash=True)
class PropertyTypeNotSupportedWarning(PropertyWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}. This will be ignored."""

    property_type: str


@dataclass(unsafe_hash=True)
class PropertyNotFoundWarning(PropertyWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name} referred
    to by {referred_type} {referred_by} does not exist. This will be ignored.
    """

    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"
    referred_by: T_ReferenceIdentifier
    referred_type: ResourceType


@dataclass(unsafe_hash=True)
class PropertyDefinitionDuplicatedWarning(PropertyWarning[T_Identifier]):
    """Got multiple values for the {resource_type} {identifier}.{property_name} {values}.
    {default_action}"""

    extra = "Recommended action: {recommended_action}"

    values: frozenset[str]
    default_action: str
    recommended_action: str | None = None


@dataclass(unsafe_hash=True)
class PropertyValueTypeUndefinedWarning(PropertyWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    which has undefined value type. This may result in unexpected behavior when exporting rules.
    {default_action}"""

    extra = "Recommended action: {recommended_action}"

    default_action: str
    recommended_action: str | None = None


@dataclass(unsafe_hash=True)
class PropertyOverwritingWarning(PropertyWarning[T_Identifier]):
    """Overwriting the {overwriting} for {property_name} in the {resource_type}
    with identifier {identifier}."""

    overwriting: tuple[str, ...]


@dataclass(unsafe_hash=True)
class PropertyDataTypeConversionWarning(PropertyWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} failed to convert the property {property_name}: {error}"""

    error: str


@dataclass(unsafe_hash=True)
class PropertyDirectRelationLimitWarning(PropertyWarning[T_Identifier]):
    """The listable direct relation property {property_name} in the {resource_type} with identifier {identifier}
    has more than {limit} relations. The relations will be sorted by (space, externalId) and truncated."""

    resource_type = "view"

    limit: int = DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT


@dataclass(unsafe_hash=True)
class PropertyMultipleValueWarning(PropertyWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name} with multiple values.
    Selecting the first value {value}, the rest will be ignored."""

    value: str
