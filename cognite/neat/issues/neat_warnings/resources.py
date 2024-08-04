from dataclasses import dataclass
from typing import Generic

from cognite.neat.issues._base import NeatWarning, T_Identifier, T_ReferenceIdentifier


# Name NeatResourceWarning to avoid conflicts with the built-in ResourceWarning
@dataclass(frozen=True)
class NeatResourceWarning(NeatWarning, Generic[T_Identifier]):
    """Base class for resource warnings {resource_type} with identifier {identifier}"""

    identifier: T_Identifier
    resource_type: str


@dataclass(frozen=True)
class ResourceNotFoundWarning(NeatResourceWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} does not exist.
    This will be ignored."""

    fix = "Create the {resource_type}"

    referred_by: T_ReferenceIdentifier
    referred_type: str


@dataclass(frozen=True)
class MultipleResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Multiple resources of type {resource_type} with identifiers {resources} were found. This will be ignored."""

    fix = "Remove the duplicate resources"

    resources: frozenset[T_Identifier]
    resource_type: str


@dataclass(frozen=True)
class FailedLoadingResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Failed to load resources of type {resource_type} with identifiers {resources}. Continuing without
    these resources."""

    extra = "The error was: {error}"

    fix = "Check the error."

    resources: frozenset[T_Identifier]
    resource_type: str
    error: str | None = None


class ResourceTypeNotSupportedWarning(NeatResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is not supported. This will be ignored."""

    ...
