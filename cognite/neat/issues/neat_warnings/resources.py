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
class DuplicatedResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Duplicated {resource_type} with identifiers {resources} were found. {default_action}"""

    fix = "Remove the duplicate resources"

    resources: frozenset[T_Identifier]
    resource_type: str
    default_action: str


@dataclass(frozen=True)
class FailedRetrievingResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Failed to retrieve {resource_type} with identifiers {resources}. Continuing without
    these resources."""

    extra = "The error was: {error}"

    fix = "Check the error."

    resources: frozenset[T_Identifier]
    resource_type: str
    error: str | None = None


class ResourceTypeNotSupportedWarning(NeatResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is not supported. This will be ignored."""

    ...
