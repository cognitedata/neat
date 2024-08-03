from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

from cognite.neat.issues import NeatWarning

T_Identifier = TypeVar("T_Identifier", bound=Hashable)

T_ReferenceIdentifier = TypeVar("T_ReferenceIdentifier", bound=Hashable)


@dataclass(frozen=True)
class ResourceWarning(NeatWarning, Generic[T_Identifier]):
    """Base class for resource warnings {resource_type} with identifier {identifier}"""

    identifier: T_Identifier
    resource_type: str


@dataclass(frozen=True)
class ResourceNotFoundWarning(ResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is missing: {reason}. This will be ignored."""

    fix = "Check the {resource_type} {identifier} and try again."
    reason: str


@dataclass(frozen=True)
class ReferredResourceNotFoundWarning(ResourceWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
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


class ResourceTypeNotSupportedWarning(ResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is not supported. This will be ignored."""

    ...
