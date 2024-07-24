from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from cognite.neat.issues import NeatWarning

T_Identifier = TypeVar("T_Identifier", bound=Hashable)

T_ReferenceIdentifier = TypeVar("T_ReferenceIdentifier", bound=Hashable)


@dataclass(frozen=True)
class ResourceWarning(NeatWarning, Generic[T_Identifier]):
    """Base class for resource warnings"""

    identifier: T_Identifier
    resource_type: str


@dataclass(frozen=True)
class ResourceNotFoundWarning(ResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is missing: {reason}. This will be ignored."""

    fix = "Check the {resource_type} {identifier} and try again."
    reason: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), reason=self.reason
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class ReferredResourceNotFoundWarning(ResourceWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} does not exist.
    This will be ignored."""

    fix = "Create the {resource_type}"

    referred_by: T_ReferenceIdentifier
    referred_type: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            referred_type=self.referred_type,
            referred_by=repr(self.referred_by),
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["referred_by"] = self.referred_by
        output["referred_type"] = self.referred_type
        return output


@dataclass(frozen=True)
class MultipleResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Multiple resources of type {resource_type} with identifiers {resources} were found. This will be ignored."""

    fix = "Remove the duplicate resources"

    resources: frozenset[T_Identifier]
    resource_type: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            resources=self.resources,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["resources"] = self.resources
        return output


@dataclass(frozen=True)
class FailedLoadingResourcesWarning(NeatWarning, Generic[T_Identifier]):
    """Failed to load resources of type {resource_type} with identifiers {resources}. Continuing without
    these resources."""

    extra = "The error was: {error}"

    fix = "Check the error."

    resources: frozenset[T_Identifier]
    resource_type: str
    error: str | None = None

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            resources=self.resources,
        ) + (self.extra.format(error=self.error) if self.error else "")

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["resources"] = self.resources
        return output


class ResourceTypeNotSupportedWarning(ResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} is not supported. This will be ignored."""

    def message(self) -> str:
        return (self.__doc__ or "").format(resource_type=self.resource_type, identifier=repr(self.identifier))

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        return output
