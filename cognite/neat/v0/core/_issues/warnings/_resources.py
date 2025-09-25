from dataclasses import dataclass
from typing import Generic

from cognite.neat.v0.core._issues._base import (
    NeatWarning,
    ResourceType,
    T_Identifier,
    T_ReferenceIdentifier,
)


# Name ResourceNeatWarning to avoid conflicts with the built-in ResourceWarning
@dataclass(unsafe_hash=True)
class ResourceNeatWarning(NeatWarning, Generic[T_Identifier]):
    """Base class for resource warnings {resource_type} with identifier {identifier}"""

    identifier: T_Identifier
    resource_type: ResourceType


@dataclass(unsafe_hash=True)
class ResourceRegexViolationWarning(ResourceNeatWarning):
    """The {resource_type} with identifier {identifier} in the {location} is violating
    the CDF regex {regex}. This will lead to errors when converting to DMS data model.
    """

    fix = (
        "Either export the data model and make the necessary changes manually"
        " or run fix.data_model.cdf_compliant_external_ids."
    )

    location: str
    regex: str


@dataclass(unsafe_hash=True)
class ResourceNotFoundWarning(ResourceNeatWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} does not exist.
    This will be ignored."""

    fix = "Create the {resource_type}"

    referred_by: T_ReferenceIdentifier
    referred_type: str


@dataclass(unsafe_hash=True)
class ResourceUnknownWarning(ResourceNeatWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} is unknown.
    Will continue, but the model is incomplete."""

    referred_by: T_ReferenceIdentifier
    referred_type: str

    fix = "You can maybe retrieve the resource from the CDF."


@dataclass(unsafe_hash=True)
class ResourceNotDefinedWarning(ResourceNeatWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} {identifier} is not defined in the {location}"""

    extra = "{column_name} {row_number} in {sheet_name}"
    fix = "Define the {resource_type} {identifier} in {location}."

    location: str
    column_name: str | None = None
    row_number: int | None = None
    sheet_name: str | None = None


@dataclass(unsafe_hash=True)
class ResourceRedefinedWarning(ResourceNeatWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} {identifier} feature {feature} is being redefine from {current_value} to {new_value}.
    This will be ignored."""

    fix = "Avoid redefinition {resource_type} features"
    feature: str
    current_value: str
    new_value: str


@dataclass(unsafe_hash=True)
class ResourcesDuplicatedWarning(NeatWarning, Generic[T_Identifier]):
    """Duplicated {resource_type} with identifiers {resources} were found. {default_action}"""

    fix = "Remove the duplicate resources"

    resources: frozenset[T_Identifier]
    resource_type: ResourceType
    default_action: str


@dataclass(unsafe_hash=True)
class ResourceRetrievalWarning(NeatWarning, Generic[T_Identifier]):
    """Failed to retrieve {resource_type} with identifier(s) {resources}. Continuing without
    these resources."""

    extra = "The error was: {error}"

    fix = "Check the error and fix accordingly."

    resources: frozenset[T_Identifier]
    resource_type: ResourceType
    error: str | None = None


class ResourceTypeNotSupportedWarning(ResourceNeatWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is not supported. This will be ignored."""

    resource_type: str  # type: ignore[assignment]
